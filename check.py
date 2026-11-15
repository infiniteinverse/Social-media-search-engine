#!/usr/bin/env python3
"""Environment check: verifies .env values, the Postgres connection/schema, and X API auth.

    python check.py              # check everything
    python check.py --skip-api   # DB only (no X API call)
"""
import argparse
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

OK, BAD, WARN = "[ ok ]", "[FAIL]", "[warn]"
EXPECTED_TABLES = ["users", "tweets", "hashtags", "topics", "tweet_topics"]
failures = 0


def report(flag: str, msg: str) -> None:
    global failures
    if flag == BAD:
        failures += 1
    print(f"{flag} {msg}")


def check_env() -> None:
    for var in ("DATABASE_URL", "X_BEARER_TOKEN"):
        val = os.getenv(var)
        if not val or "PASTE_YOUR" in val:
            report(WARN if var == "X_BEARER_TOKEN" else BAD, f"{var} is not set (see .env.example)")
        else:
            report(OK, f"{var} is set")


def check_db() -> None:
    try:
        import psycopg2
        conn = psycopg2.connect(os.environ["DATABASE_URL"])
    except KeyError:
        report(BAD, "cannot test database: DATABASE_URL missing")
        return
    except Exception as exc:  # noqa: BLE001
        report(BAD, f"database connection failed: {exc}".strip())
        return
    with conn, conn.cursor() as cur:
        cur.execute("SHOW server_version")
        report(OK, f"connected to PostgreSQL {cur.fetchone()[0]}")
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        present = {r[0] for r in cur.fetchall()}
        missing = [t for t in EXPECTED_TABLES if t not in present]
        if missing:
            report(BAD, f"missing tables: {', '.join(missing)}  ->  psql \"$DATABASE_URL\" -f db/create_schema.sql")
            return
        report(OK, "all 5 tables exist")
        for t in EXPECTED_TABLES:  # table names come from the constant list above
            cur.execute(f"SELECT count(*) FROM {t}")
            print(f"        {t:<13}{cur.fetchone()[0]:>8,} rows")
    conn.close()


def check_api() -> None:
    token = os.getenv("X_BEARER_TOKEN", "")
    if not token or "PASTE_YOUR" in token:
        report(WARN, "skipping API check (no bearer token). Mock mode still works.")
        return
    try:
        r = requests.get(
            "https://api.x.com/2/tweets/search/recent",
            params={"query": "python -is:retweet", "max_results": 10},
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        report(BAD, f"could not reach X API: {exc}")
        return
    left, limit = r.headers.get("x-rate-limit-remaining"), r.headers.get("x-rate-limit-limit")
    if r.status_code == 200:
        report(OK, f"X API auth works (HTTP 200, rate limit {left}/{limit} left this window)")
    elif r.status_code == 429:
        report(WARN, "authenticated but rate-limited right now (HTTP 429). Backoff logic will handle this.")
    elif r.status_code in (401, 403):
        report(BAD, f"HTTP {r.status_code}: token invalid or plan lacks recent-search access. {r.text[:140]}")
    else:
        report(BAD, f"unexpected HTTP {r.status_code}: {r.text[:140]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-api", action="store_true")
    args = ap.parse_args()
    print("Tweet Archive - environment check\n")
    check_env()
    check_db()
    if not args.skip_api:
        check_api()
    print()
    print("All good." if not failures else f"{failures} problem(s) found.")
    sys.exit(1 if failures else 0)
