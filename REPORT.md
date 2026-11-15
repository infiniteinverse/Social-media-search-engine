# Tweet Archive: One-Page Report

## 1. Schema design
Five tables in third normal form. Every fact is stored once and linked by key.

| Table | Key | Purpose |
|---|---|---|
| `users` | `user_id` | One row per account: username, display name, followers, verified |
| `tweets` | `tweet_id` → FK `users` | Text, timestamp, language, like/retweet/reply/quote counts |
| `hashtags` | (`tweet_id`, `tag`) | One-to-many from tweets; tags stored lower-case without `#` |
| `topics` | `topic_id` | One row per ingestion run (query string, `run_at`) |
| `tweet_topics` | (`topic_id`, `tweet_id`) | Many-to-many: which run found which tweet |

* X IDs are stored as `TEXT` (they exceed safe integer ranges in some clients).
* `CHECK` constraints keep counts non-negative; foreign keys use `ON DELETE CASCADE` for child rows.
* Indexes back every search filter: `created_at`, `lang`, `lower(username)`, `hashtags(tag)`, and a
  trigram GIN index on `tweets.text` so `ILIKE '%term%'` stays fast.
* UPSERT strategy: `ON CONFLICT` on primary keys. Tweet metrics and user profiles are refreshed on
  re-ingest; hashtag and topic links use `DO NOTHING`. The whole load runs in one transaction.

## 2. API endpoints used
* **`GET https://api.x.com/2/tweets/search/recent`** (X API v2, app-only Bearer token).
  * `query` (with optional `lang:xx`, `-is:retweet`), `max_results` (10–100 per page),
    `start_time`, `end_time`, `next_token` for pagination.
  * `tweet.fields=created_at,public_metrics,lang,entities,author_id`,
    `user.fields=created_at,public_metrics,username,name,verified`, `expansions=author_id`.
* Parsing: `data[]` → tweets, `includes.users[]` → users, `data[].entities.hashtags[]` → hashtags.
* A mock mode (`--from-file`) feeds the same parser from a saved payload, so the pipeline is
  testable without API access.

## 3. Rate-limit handling
* **HTTP 429:** read the `x-rate-limit-reset` header and sleep until that epoch (capped at 15 min,
  60 s fallback), then retry the same page.
* **Proactive:** if `x-rate-limit-remaining` reaches 0 on a successful call, wait for the reset
  before the next request.
* **HTTP 5xx / network errors:** exponential back-off with jitter, up to 5 attempts.
* **HTTP 401/403:** fail fast with a clear message (bad token or plan without search access).
* The retry loop is iterative, not recursive, so long waits cannot overflow the stack. The run
  summary reports API requests made and rate-limit waits.

## 4. Web search and safe SQL
* Filters: text, hashtag(s), username, date range, language, min-likes, ingestion run, sort, page size.
* Every value is a **bound parameter**. ORDER BY is chosen from a whitelist dictionary; LIKE
  wildcards are escaped; the date range uses a half-open interval (`>= start`, `< end + 1 day`).
* Pagination uses `LIMIT/OFFSET` with a separate `count(*)` for page totals.
* Active filters render as removable chips, and the results page can show the exact SQL plus its
  parameters. Jinja2 auto-escaping prevents stored-XSS from tweet text.
