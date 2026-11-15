#!/usr/bin/env python3
"""Fetch tweets from the X API v2 (recent search) and load them into PostgreSQL.

Examples
--------
    python ingest/fetch_and_load.py --query "generative ai" --lang en --max 200
    python ingest/fetch_and_load.py --query "#python" --start 2026-11-08T00:00:00Z
    python ingest/fetch_and_load.py --query "generative ai" --from-file ingest/sample_payload.json

Pipeline
--------
    X API  ->  paginate (next_token)  ->  parse (tweet / user / hashtags)
           ->  UPSERT (ON CONFLICT)   ->  link tweets to this run (tweet_topics)

Rate limits
-----------
* HTTP 429  -> sleep until the `x-rate-limit-reset` epoch (fallback 60 s), then retry.
* Remaining quota == 0 on a 200 -> proactively sleep until reset.
* HTTP 5xx / network errors -> exponential back-off with jitter, max 5 attempts.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import requests
from dotenv import load_dotenv
from psycopg2.extras import execute_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from db.connect import get_conn  # noqa: E402  (needs sys.path tweak above)

SEARCH_URL = "https://api.x.com/2/tweets/search/recent"
MAX_RETRIES = 5
API_PAGE_MIN, API_PAGE_MAX = 10, 100  # limits of the recent-search endpoint

TWEET_FIELDS = "created_at,public_metrics,lang,entities,author_id"
USER_FIELDS = "created_at,public_metrics,username,name,verified"

log = logging.getLogger("ingest")


# --------------------------------------------------------------------------- #
#  Pretty terminal output (makes the screenshot readable)
# --------------------------------------------------------------------------- #
class C:
    on = sys.stdout.isatty()
    reset, bold, dim = ("\033[0m", "\033[1m", "\033[2m") if on else ("", "", "")
    blue, green, amber, red = (
        ("\033[38;5;105m", "\033[38;5;42m", "\033[38;5;214m", "\033[38;5;203m")
        if on
        else ("", "", "", "")
    )


def banner(title: str, rows: list[tuple[str, str]]) -> None:
    width = 62
    print(f"{C.blue}+{'-' * (width - 2)}+{C.reset}")
    print(f"{C.blue}|{C.reset} {C.bold}{title:<{width - 4}}{C.reset} {C.blue}|{C.reset}")
    print(f"{C.blue}+{'-' * (width - 2)}+{C.reset}")
    for k, v in rows:
        line = f"{k:<16}{v}"
        print(f"{C.blue}|{C.reset} {line:<{width - 4}} {C.blue}|{C.reset}")
    print(f"{C.blue}+{'-' * (width - 2)}+{C.reset}")


# --------------------------------------------------------------------------- #
#  API client
# --------------------------------------------------------------------------- #
class XApiError(RuntimeError):
    pass


class XClient:
    def __init__(self, bearer_token: str):
        if not bearer_token:
            raise XApiError("X_BEARER_TOKEN is missing. Set it in .env (see .env.example).")
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {bearer_token}"})
        self.requests_made = 0
        self.rate_limit_sleeps = 0

    @staticmethod
    def _sleep_until(epoch: int | None, fallback: int = 60, cap: int = 900) -> int:
        wait = (epoch - int(time.time()) + 1) if epoch else fallback
        wait = max(1, min(wait, cap))
        log.warning("rate limit reached, sleeping %ss", wait)
        time.sleep(wait)
        return wait

    def get(self, params: dict[str, Any]) -> dict[str, Any]:
        """GET one page with retry / back-off. Iterative (no recursion)."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                r = self.session.get(SEARCH_URL, params=params, timeout=30)
            except requests.RequestException as exc:
                delay = min(2 ** attempt + random.random(), 60)
                log.warning("network error (%s); retry %d/%d in %.1fs", exc, attempt, MAX_RETRIES, delay)
                time.sleep(delay)
                continue

            self.requests_made += 1
            reset = r.headers.get("x-rate-limit-reset")
            remaining = r.headers.get("x-rate-limit-remaining")
            reset_epoch = int(reset) if reset and reset.isdigit() else None

            if r.status_code == 200:
                if remaining is not None and remaining.isdigit() and int(remaining) == 0:
                    self.rate_limit_sleeps += 1
                    self._sleep_until(reset_epoch)
                return r.json()

            if r.status_code == 429:
                self.rate_limit_sleeps += 1
                self._sleep_until(reset_epoch)
                continue

            if r.status_code >= 500:
                delay = min(2 ** attempt + random.random(), 60)
                log.warning("server error %s; retry %d/%d in %.1fs", r.status_code, attempt, MAX_RETRIES, delay)
                time.sleep(delay)
                continue

            if r.status_code in (401, 403):
                raise XApiError(
                    f"HTTP {r.status_code}: token rejected or your X API plan has no access to "
                    f"recent search. Response: {r.text[:200]}. "
                    "Use --from-file ingest/sample_payload.json to run in mock mode."
                )
            raise XApiError(f"HTTP {r.status_code}: {r.text[:300]}")

        raise XApiError(f"gave up after {MAX_RETRIES} attempts")


def paginate(
    client: XClient,
    query: str,
    total: int,
    start: str | None,
    end: str | None,
) -> Iterator[dict[str, Any]]:
    """Yield API pages until `total` tweets are collected or results run out."""
    collected, next_token = 0, None
    while collected < total:
        page_size = max(API_PAGE_MIN, min(API_PAGE_MAX, total - collected))
        params: dict[str, Any] = {
            "query": query,
            "max_results": page_size,
            "tweet.fields": TWEET_FIELDS,
            "user.fields": USER_FIELDS,
            "expansions": "author_id",
        }
        if start:
            params["start_time"] = start
        if end:
            params["end_time"] = end
        if next_token:
            params["next_token"] = next_token

        page = client.get(params)
        got = len(page.get("data", []))
        collected += got
        log.info("page fetched: %d tweets (running total %d)", got, collected)
        yield page

        next_token = page.get("meta", {}).get("next_token")
        if not next_token or got == 0:
            break


# --------------------------------------------------------------------------- #
#  Parsing
# --------------------------------------------------------------------------- #
@dataclass
class Parsed:
    users: dict[str, tuple] = field(default_factory=dict)
    tweets: dict[str, tuple] = field(default_factory=dict)
    hashtags: set[tuple[str, str]] = field(default_factory=set)


def parse_pages(pages: Iterator[dict[str, Any]]) -> Parsed:
    out = Parsed()
    for page in pages:
        for u in page.get("includes", {}).get("users", []):
            pm = u.get("public_metrics", {})
            out.users[u["id"]] = (
                u["id"],
                u.get("username"),
                u.get("name"),
                u.get("created_at"),
                pm.get("followers_count"),
                bool(u.get("verified", False)),
            )
        for t in page.get("data", []):
            m = t.get("public_metrics", {})
            out.tweets[t["id"]] = (
                t["id"],
                t["author_id"],
                t["text"],
                t["created_at"],
                t.get("lang"),
                m.get("like_count", 0),
                m.get("retweet_count", 0),
                m.get("reply_count", 0),
                m.get("quote_count", 0),
            )
            for h in t.get("entities", {}).get("hashtags", []):
                out.hashtags.add((t["id"], h["tag"].lower()))
    return out


# --------------------------------------------------------------------------- #
#  Loading (UPSERT)
# --------------------------------------------------------------------------- #
def upsert(conn, parsed: Parsed, topic_query: str) -> dict[str, int]:
    """Write everything in ONE transaction; re-running is safe (idempotent)."""
    with conn:  # commit on success, rollback on exception
        with conn.cursor() as cur:
            cur.execute("INSERT INTO topics (query) VALUES (%s) RETURNING topic_id", (topic_query,))
            topic_id = cur.fetchone()[0]

            # authors referenced by a tweet but missing from `includes` -> stub rows
            missing = {t[1] for t in parsed.tweets.values()} - parsed.users.keys()
            if missing:
                execute_values(
                    cur,
                    "INSERT INTO users (user_id) VALUES %s ON CONFLICT (user_id) DO NOTHING",
                    [(uid,) for uid in missing],
                )

            if parsed.users:
                execute_values(
                    cur,
                    """
                    INSERT INTO users (user_id, username, display_name, created_at, followers_count, verified)
                    VALUES %s
                    ON CONFLICT (user_id) DO UPDATE SET
                        username        = EXCLUDED.username,
                        display_name    = EXCLUDED.display_name,
                        created_at      = EXCLUDED.created_at,
                        followers_count = EXCLUDED.followers_count,
                        verified        = EXCLUDED.verified
                    """,
                    list(parsed.users.values()),
                )

            if parsed.tweets:
                execute_values(
                    cur,
                    """
                    INSERT INTO tweets (tweet_id, user_id, text, created_at, lang,
                                        like_count, retweet_count, reply_count, quote_count)
                    VALUES %s
                    ON CONFLICT (tweet_id) DO UPDATE SET
                        like_count    = EXCLUDED.like_count,
                        retweet_count = EXCLUDED.retweet_count,
                        reply_count   = EXCLUDED.reply_count,
                        quote_count   = EXCLUDED.quote_count
                    """,
                    list(parsed.tweets.values()),
                )

            if parsed.hashtags:
                execute_values(
                    cur,
                    "INSERT INTO hashtags (tweet_id, tag) VALUES %s ON CONFLICT DO NOTHING",
                    sorted(parsed.hashtags),
                )

            if parsed.tweets:
                execute_values(
                    cur,
                    "INSERT INTO tweet_topics (topic_id, tweet_id) VALUES %s ON CONFLICT DO NOTHING",
                    [(topic_id, tid) for tid in parsed.tweets],
                )

    return {
        "topic_id": topic_id,
        "tweets": len(parsed.tweets),
        "users": len(parsed.users),
        "hashtags": len(parsed.hashtags),
    }


# --------------------------------------------------------------------------- #
#  CLI
# --------------------------------------------------------------------------- #
def load_mock(path: str) -> Iterator[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    yield from (data if isinstance(data, list) else [data])


def build_query(query: str, lang: str | None, exclude_retweets: bool) -> str:
    parts = [query.strip()]
    if lang and "lang:" not in query:
        parts.append(f"lang:{lang}")
    if exclude_retweets and "is:retweet" not in query:
        parts.append("-is:retweet")
    return " ".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch tweets from X API v2 and load them into Postgres.")
    ap.add_argument("--query", required=True, help='topic / X search query, e.g. "generative ai"')
    ap.add_argument("--max", type=int, default=50, help="total tweets to collect (default 50)")
    ap.add_argument("--lang", help="ISO language code appended as lang:xx")
    ap.add_argument("--start", help="ISO-8601 start_time, e.g. 2026-11-08T00:00:00Z")
    ap.add_argument("--end", help="ISO-8601 end_time")
    ap.add_argument("--keep-retweets", action="store_true", help="do not append -is:retweet")
    ap.add_argument("--from-file", help="mock mode: load a saved API payload instead of calling X")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format=f"{C.dim}%(asctime)s{C.reset} %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )

    full_query = build_query(args.query, args.lang, not args.keep_retweets)
    mode = "MOCK  (file)" if args.from_file else "LIVE  (X API v2)"
    banner(
        "Tweet ingestion",
        [("mode", mode), ("query", full_query), ("max results", str(args.max)),
         ("window", f"{args.start or 'last 7 days'} -> {args.end or 'now'}")],
    )

    started = time.time()
    client = None
    try:
        if args.from_file:
            pages = load_mock(args.from_file)
        else:
            client = XClient(os.getenv("X_BEARER_TOKEN", ""))
            pages = paginate(client, full_query, args.max, args.start, args.end)
        parsed = parse_pages(pages)
    except XApiError as exc:
        log.error("%s", exc)
        return 2

    if not parsed.tweets:
        log.warning("API returned no tweets for this query. Nothing to store.")
        return 0

    conn = get_conn()
    try:
        stats = upsert(conn, parsed, full_query)
    finally:
        conn.close()

    elapsed = time.time() - started
    print()
    banner(
        "Done",
        [("topic_id", str(stats["topic_id"])),
         ("tweets upserted", str(stats["tweets"])),
         ("users upserted", str(stats["users"])),
         ("hashtag links", str(stats["hashtags"])),
         ("API requests", str(client.requests_made if client else 0)),
         ("rate-limit waits", str(client.rate_limit_sleeps if client else 0)),
         ("elapsed", f"{elapsed:.1f}s")],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
