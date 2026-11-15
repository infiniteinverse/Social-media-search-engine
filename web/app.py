"""Flask web app: search stored tweets with safe, parameterized SQL.

Routes
------
GET /            search form + results table (filters live in the query string)
POST /search     same form submitted via POST -> redirected to GET / (shareable URL)
GET /api/search  the same search as JSON
GET /healthz     DB connectivity probe

Security notes
--------------
* Every user value reaches PostgreSQL as a bound parameter (`%s`).
* The only text spliced into SQL are *constant fragments chosen by this file*
  (WHERE clauses, ORDER BY keys looked up in a whitelist dict).
* LIKE wildcards typed by the user (% _ \\) are escaped so they match literally.
* Jinja2 auto-escapes all output, so stored tweet text cannot inject HTML.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import psycopg2
from flask import Flask, jsonify, redirect, render_template, request, url_for
from markupsafe import Markup, escape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from db.connect import cursor  # noqa: E402

app = Flask(__name__)

PER_PAGE_CHOICES = (10, 25, 50)
DEFAULT_PER_PAGE = 10

# ORDER BY fragments are looked up here -- user input is never interpolated.
SORTS: dict[str, tuple[str, str]] = {
    "newest": ("Newest first", "t.created_at DESC, t.tweet_id DESC"),
    "oldest": ("Oldest first", "t.created_at ASC, t.tweet_id ASC"),
    "likes": ("Most liked", "t.like_count DESC, t.created_at DESC"),
    "retweets": ("Most retweeted", "t.retweet_count DESC, t.created_at DESC"),
}

BASE_FROM = "FROM tweets t JOIN users u ON u.user_id = t.user_id"


# --------------------------------------------------------------------------- #
#  Input handling
# --------------------------------------------------------------------------- #
def like_escape(value: str) -> str:
    """Escape LIKE metacharacters so user input matches literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def parse_date(raw: str, errors: list[str], label: str) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        errors.append(f"{label} “{raw}” is not a valid date (use YYYY-MM-DD).")
        return None


def parse_int(raw: str, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(raw)))
    except (TypeError, ValueError):
        return default


@dataclass
class Search:
    """Normalised filters + the SQL pieces they generate."""

    q: str = ""
    hashtags: list[str] = field(default_factory=list)
    username: str = ""
    start: date | None = None
    end: date | None = None
    lang: str = ""
    topic: int | None = None
    min_likes: int = 0
    sort: str = "newest"
    per_page: int = DEFAULT_PER_PAGE
    page: int = 1
    errors: list[str] = field(default_factory=list)

    @classmethod
    def from_args(cls, args) -> "Search":
        s = cls()
        s.q = args.get("q", "").strip()[:200]
        raw_tags = args.get("hashtag", "")
        s.hashtags = [
            t.lstrip("#").strip().lower()
            for t in re.split(r"[,\s]+", raw_tags)
            if t.strip().lstrip("#")
        ][:10]
        s.username = args.get("username", "").strip().lstrip("@")[:50]
        s.start = parse_date(args.get("start_date", "").strip(), s.errors, "Start date")
        s.end = parse_date(args.get("end_date", "").strip(), s.errors, "End date")
        if s.start and s.end and s.start > s.end:
            s.errors.append("Start date is after end date; the two were swapped.")
            s.start, s.end = s.end, s.start
        s.lang = re.sub(r"[^a-zA-Z\-]", "", args.get("lang", ""))[:8].lower()
        topic = args.get("topic", "")
        s.topic = int(topic) if topic.isdigit() else None
        s.min_likes = parse_int(args.get("min_likes", "0"), 0, 0, 10_000_000)
        s.sort = args.get("sort", "newest") if args.get("sort") in SORTS else "newest"
        s.per_page = parse_int(args.get("per_page", ""), DEFAULT_PER_PAGE, 1, 50)
        if s.per_page not in PER_PAGE_CHOICES:
            s.per_page = DEFAULT_PER_PAGE
        s.page = parse_int(args.get("page", "1"), 1, 1, 100_000)
        return s

    # -- SQL ---------------------------------------------------------------
    def where(self) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if self.q:
            clauses.append("t.text ILIKE %s")
            params.append(f"%{like_escape(self.q)}%")
        if self.hashtags:
            clauses.append(
                "EXISTS (SELECT 1 FROM hashtags h2 "
                "WHERE h2.tweet_id = t.tweet_id AND h2.tag = ANY(%s))"
            )
            params.append(self.hashtags)
        if self.username:
            clauses.append("u.username ILIKE %s")
            params.append(f"%{like_escape(self.username)}%")
        if self.start:
            clauses.append("t.created_at >= %s")
            params.append(datetime.combine(self.start, time.min, tzinfo=timezone.utc))
        if self.end:  # inclusive end date -> strictly before the next midnight
            clauses.append("t.created_at < %s")
            params.append(datetime.combine(self.end + timedelta(days=1), time.min, tzinfo=timezone.utc))
        if self.lang:
            clauses.append("t.lang = %s")
            params.append(self.lang)
        if self.topic is not None:
            clauses.append("EXISTS (SELECT 1 FROM tweet_topics tt WHERE tt.tweet_id = t.tweet_id AND tt.topic_id = %s)")
            params.append(self.topic)
        if self.min_likes:
            clauses.append("t.like_count >= %s")
            params.append(self.min_likes)
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params

    # -- Human-readable chips (with a link that removes that one filter) ---
    def chips(self, topics: dict[int, str]) -> list[dict[str, str]]:
        base = self.as_args()
        defs = [
            ("q", "Text contains", f"“{self.q}”" if self.q else ""),
            ("hashtag", "Hashtag", ", ".join("#" + t for t in self.hashtags)),
            ("username", "Username", f"@{self.username}" if self.username else ""),
            ("start_date", "From", self.start.isoformat() if self.start else ""),
            ("end_date", "Until", self.end.isoformat() if self.end else ""),
            ("lang", "Language", self.lang),
            ("topic", "Topic run", topics.get(self.topic, f"#{self.topic}") if self.topic is not None else ""),
            ("min_likes", "Likes ≥", f"{self.min_likes:,}" if self.min_likes else ""),
        ]
        chips = []
        for key, label, value in defs:
            if value:
                rest = {k: v for k, v in base.items() if k != key}
                chips.append({"label": label, "value": value, "remove": url_for("index", **rest)})
        return chips

    def as_args(self, **override: Any) -> dict[str, Any]:
        d: dict[str, Any] = {
            "q": self.q,
            "hashtag": ", ".join(self.hashtags),
            "username": self.username,
            "start_date": self.start.isoformat() if self.start else "",
            "end_date": self.end.isoformat() if self.end else "",
            "lang": self.lang,
            "topic": self.topic if self.topic is not None else "",
            "min_likes": self.min_likes or "",
            "sort": self.sort,
            "per_page": self.per_page,
        }
        d.update(override)
        return {k: v for k, v in d.items() if v not in ("", None)}


# --------------------------------------------------------------------------- #
#  Query execution
# --------------------------------------------------------------------------- #
def run_search(s: Search) -> dict[str, Any]:
    where_sql, params = s.where()
    order_sql = SORTS[s.sort][1]  # whitelisted constant

    rows_sql = (
        "SELECT t.tweet_id, t.created_at, u.username, u.display_name, u.verified, "
        "t.text, t.lang, t.like_count, t.retweet_count, t.reply_count, "
        "ARRAY(SELECT h.tag FROM hashtags h WHERE h.tweet_id = t.tweet_id ORDER BY h.tag) AS hashtags "
        f"{BASE_FROM}{where_sql} ORDER BY {order_sql} LIMIT %s OFFSET %s"
    )
    stats_sql = (
        "SELECT count(*) AS total, count(DISTINCT t.user_id) AS authors, "
        "COALESCE(sum(t.like_count), 0) AS likes, COALESCE(sum(t.retweet_count), 0) AS retweets "
        f"{BASE_FROM}{where_sql}"
    )
    tags_sql = (
        "SELECT h.tag, count(*) AS n "
        f"{BASE_FROM} JOIN hashtags h ON h.tweet_id = t.tweet_id{where_sql} "
        "GROUP BY h.tag ORDER BY n DESC, h.tag LIMIT 6"
    )
    daily_sql = (
        "SELECT (t.created_at AT TIME ZONE 'UTC')::date AS day, count(*) AS n "
        f"{BASE_FROM}{where_sql} GROUP BY day ORDER BY day DESC LIMIT 30"
    )

    with cursor() as cur:
        cur.execute(stats_sql, params)
        stats = cur.fetchone()
        s.page = min(s.page, max(1, -(-stats["total"] // s.per_page)))  # clamp page
        offset = (s.page - 1) * s.per_page
        cur.execute(rows_sql, params + [s.per_page, offset])
        rows = cur.fetchall()
        cur.execute(tags_sql, params)
        top_tags = cur.fetchall()
        cur.execute(daily_sql, params)
        daily = list(reversed(cur.fetchall()))

    total = stats["total"]
    pages = max(1, -(-total // s.per_page))
    return {
        "rows": rows,
        "stats": stats,
        "top_tags": top_tags,
        "daily": daily,
        "pages": pages,
        "sql": rows_sql,
        "params": params + [s.per_page, (s.page - 1) * s.per_page],
    }


def lookups() -> dict[str, Any]:
    with cursor() as cur:
        cur.execute("SELECT lang, count(*) AS n FROM tweets WHERE lang IS NOT NULL GROUP BY lang ORDER BY n DESC")
        langs = cur.fetchall()
        cur.execute(
            "SELECT tp.topic_id, tp.query, tp.run_at, count(tt.tweet_id) AS n "
            "FROM topics tp LEFT JOIN tweet_topics tt USING (topic_id) "
            "GROUP BY tp.topic_id ORDER BY tp.run_at DESC LIMIT 20"
        )
        topics = cur.fetchall()
        cur.execute("SELECT count(*) AS tweets, (SELECT count(*) FROM users) AS users FROM tweets")
        totals = cur.fetchone()
    return {"langs": langs, "topics": topics, "totals": totals}


# --------------------------------------------------------------------------- #
#  Template helpers
# --------------------------------------------------------------------------- #
@app.template_filter("highlight")
def highlight(text: str, term: str) -> Markup:
    safe = str(escape(text))
    if not term:
        return Markup(safe)
    pattern = re.compile(re.escape(str(escape(term))), re.IGNORECASE)
    return Markup(pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", safe))


@app.template_filter("stamp")
def stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%d %b %Y, %H:%M")


@app.template_filter("compact")
def compact(n: int) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    if n >= 1_000:
        return f"{n / 1000:.1f}k"
    return str(n)


LANG_NAMES = {"en": "English", "es": "Spanish", "de": "German", "fr": "French", "hi": "Hindi",
              "ja": "Japanese", "pt": "Portuguese", "it": "Italian", "ar": "Arabic", "ru": "Russian"}


@app.template_filter("langname")
def langname(code: str) -> str:
    return LANG_NAMES.get(code, code)


# --------------------------------------------------------------------------- #
#  Routes
# --------------------------------------------------------------------------- #
@app.route("/search", methods=["POST"])
def search_post():
    s = Search.from_args(request.form)
    return redirect(url_for("index", **s.as_args()))


@app.route("/")
def index():
    s = Search.from_args(request.args)
    ctx: dict[str, Any] = {"s": s, "sorts": SORTS, "per_page_choices": PER_PAGE_CHOICES, "db_error": None}
    try:
        look = lookups()
        result = run_search(s)
    except (psycopg2.Error, RuntimeError) as exc:
        ctx["db_error"] = str(exc).strip()
        return render_template("index.html", **ctx), 503

    topic_names = {t["topic_id"]: t["query"] for t in look["topics"]}
    daily = result["daily"]
    peak = max((d["n"] for d in daily), default=1)
    tag_peak = max((t["n"] for t in result["top_tags"]), default=1)

    def page_url(p: int) -> str:
        return url_for("index", **s.as_args(page=p))

    ctx.update(
        look=look,
        r=result,
        chips=s.chips(topic_names),
        clear_url=url_for("index"),
        peak=peak,
        tag_peak=tag_peak,
        page_url=page_url,
        offset=(s.page - 1) * s.per_page,
        has_filters=bool(s.chips(topic_names)),
    )
    return render_template("index.html", **ctx)


@app.route("/api/search")
def api_search():
    s = Search.from_args(request.args)
    try:
        result = run_search(s)
    except (psycopg2.Error, RuntimeError) as exc:
        return jsonify(error=str(exc)), 503
    rows = [
        {**r, "created_at": r["created_at"].isoformat()} for r in result["rows"]
    ]
    return jsonify(total=result["stats"]["total"], page=s.page, pages=result["pages"], results=rows)


@app.route("/healthz")
def healthz():
    try:
        with cursor() as cur:
            cur.execute("SELECT 1")
        return jsonify(status="ok")
    except Exception as exc:  # noqa: BLE001
        return jsonify(status="down", detail=str(exc)), 503


if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
        port=int(os.getenv("PORT", "5000")),
    )
