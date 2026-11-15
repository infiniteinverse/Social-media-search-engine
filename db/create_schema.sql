-- =====================================================================
--  Tweet Archive  |  PostgreSQL 13+ schema (3NF, idempotent)
--  Run:  psql "$DATABASE_URL" -f db/create_schema.sql
-- =====================================================================

BEGIN;

-- Trigram index support so ILIKE '%term%' can use an index.
-- (pg_trgm is a "trusted" extension on PG13+, so the DB owner can install it.)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- users : one row per X account (author of at least one stored tweet)
CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT        PRIMARY KEY,
    username        TEXT,
    display_name    TEXT,
    created_at      TIMESTAMPTZ,
    followers_count INT         CHECK (followers_count IS NULL OR followers_count >= 0),
    verified        BOOLEAN     NOT NULL DEFAULT FALSE
);

-- tweets : one row per post; FK to its author
CREATE TABLE IF NOT EXISTS tweets (
    tweet_id      TEXT        PRIMARY KEY,
    user_id       TEXT        NOT NULL REFERENCES users(user_id),
    text          TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL,
    lang          TEXT,
    like_count    INT         NOT NULL DEFAULT 0 CHECK (like_count    >= 0),
    retweet_count INT         NOT NULL DEFAULT 0 CHECK (retweet_count >= 0),
    reply_count   INT         NOT NULL DEFAULT 0 CHECK (reply_count   >= 0),
    quote_count   INT         NOT NULL DEFAULT 0 CHECK (quote_count   >= 0)
);

-- hashtags : 1-to-many from tweets (stored lower-case, without '#')
CREATE TABLE IF NOT EXISTS hashtags (
    tweet_id TEXT NOT NULL REFERENCES tweets(tweet_id) ON DELETE CASCADE,
    tag      TEXT NOT NULL,
    PRIMARY KEY (tweet_id, tag)
);

-- topics        : every ingestion run (the query string that was searched)
-- tweet_topics  : many-to-many link, i.e. "which run found which tweet"
CREATE TABLE IF NOT EXISTS topics (
    topic_id SERIAL      PRIMARY KEY,
    query    TEXT        NOT NULL,
    run_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tweet_topics (
    topic_id INT  NOT NULL REFERENCES topics(topic_id) ON DELETE CASCADE,
    tweet_id TEXT NOT NULL REFERENCES tweets(tweet_id) ON DELETE CASCADE,
    PRIMARY KEY (topic_id, tweet_id)
);

-- Indexes that back the search form's filters
CREATE INDEX IF NOT EXISTS idx_tweets_created_at  ON tweets (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tweets_user_id     ON tweets (user_id);
CREATE INDEX IF NOT EXISTS idx_tweets_lang        ON tweets (lang);
CREATE INDEX IF NOT EXISTS idx_tweets_likes       ON tweets (like_count DESC);
CREATE INDEX IF NOT EXISTS idx_tweets_text_trgm   ON tweets USING gin (text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_users_username_lc  ON users (lower(username));
CREATE INDEX IF NOT EXISTS idx_hashtags_tag       ON hashtags (tag);
CREATE INDEX IF NOT EXISTS idx_tweet_topics_tweet ON tweet_topics (tweet_id);

COMMIT;
