#!/usr/bin/env python3
"""Generate ingest/sample_payload.json: a realistic, X-API-v2-shaped payload.

Used for mock mode (`--from-file`) so the project can be demoed and
screenshotted without paid API access. Deterministic (fixed seed).
"""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

random.seed(2026)
END = datetime(2026, 11, 14, 18, 0, tzinfo=timezone.utc)

USERS = [
    ("1001", "mira_codes", "Mira Okafor", 48210, True),
    ("1002", "devsamir", "Samir Rao", 9320, False),
    ("1003", "ailab_weekly", "AI Lab Weekly", 120400, True),
    ("1004", "priya_ml", "Priya Nair", 15780, False),
    ("1005", "tomasz_dev", "Tomasz Kowalski", 2210, False),
    ("1006", "luciaIA", "Lucía Fernández", 6540, False),
    ("1007", "hanna_data", "Hanna Weber", 3890, False),
    ("1008", "opensourcenik", "Nikhil Verma", 27100, False),
    ("1009", "the_prompt_desk", "The Prompt Desk", 88300, True),
    ("1010", "chloe_builds", "Chloe Martin", 1760, False),
    ("1011", "rahul_pythonista", "Rahul Das", 5120, False),
    ("1012", "kenji_ai", "Kenji Mori", 12040, False),
]

EN = [
    ("Just shipped a RAG pipeline that cut our support-ticket triage time by 40%. {t}", ["GenerativeAI", "RAG", "Python"]),
    ("Hot take: evaluation datasets matter more than the model you pick. Spend a week on evals. {t}", ["LLM", "MLOps"]),
    ("Open-weight models are closing the gap faster than anyone predicted a year ago. {t}", ["OpenSource", "GenerativeAI"]),
    ("Our team replaced 3 internal tools with a single agent workflow. Lessons learned in the thread. {t}", ["AI", "Agents"]),
    ("Prompt caching just halved our inference bill. If you run long system prompts, try it. {t}", ["LLM", "Python"]),
    ("Reading the new alignment paper on weak-to-strong generalization. Dense but worth it. {t}", ["AI", "Research"]),
    ("Tutorial: build a semantic search over your own notes with embeddings and Postgres pgvector. {t}", ["Postgres", "Python", "GenerativeAI"]),
    ("Anyone else seeing hallucinated citations in long-context summaries? Share your mitigations. {t}", ["LLM", "AI"]),
    ("Generative AI in the classroom: what actually helped students and what was hype. {t}", ["EdTech", "GenerativeAI"]),
    ("Fine-tuning vs. prompting vs. RAG - a decision tree I use with clients. {t}", ["LLM", "MLOps", "RAG"]),
    ("Local inference on a laptop is finally pleasant. Quantized 8B model, instant replies. {t}", ["OpenSource", "AI"]),
    ("Dataset licensing is the next big conversation for generative AI. We need clear provenance. {t}", ["GenerativeAI", "Ethics"]),
    ("Built a Flask dashboard over 10k stored tweets in an afternoon. SQL is still undefeated. {t}", ["Flask", "Postgres", "Python"]),
    ("Structured outputs made our JSON parsing bugs disappear overnight. {t}", ["LLM", "Python"]),
    ("Voice agents are the underrated frontier: latency is the whole game. {t}", ["AI", "Agents"]),
]
ES = [
    ("La IA generativa está cambiando cómo escribimos documentación técnica. {t}", ["IAgenerativa", "Desarrollo"]),
    ("Taller gratuito sobre modelos de lenguaje y Python este sábado. {t}", ["Python", "IA"]),
]
DE = [
    ("Generative KI im Mittelstand: Erste Erfahrungen aus drei Pilotprojekten. {t}", ["KI", "GenerativeAI"]),
    ("Neue Studie zeigt: Prompt-Design beeinflusst die Antwortqualität deutlich. {t}", ["KI", "LLM"]),
]
FR = [("Un guide pratique pour évaluer les modèles de langage sans benchmarks publics. {t}", ["IA", "LLM"])]
TAILS = ["", "Thoughts?", "Link in replies.", "Thread below.", "Curious what you all think.", "More soon."]


def mk_tweet(i):
    pool = random.choices([EN, ES, DE, FR], weights=[78, 8, 10, 4])[0]
    lang = {id(EN): "en", id(ES): "es", id(DE): "de", id(FR): "fr"}[id(pool)]
    text, tags = random.choice(pool)
    text = text.format(t=random.choice(TAILS)).strip()
    text = text + " " + " ".join("#" + t for t in tags)
    uid = random.choice(USERS)[0]
    created = END - timedelta(minutes=random.randint(5, 60 * 24 * 7))
    big = random.random() < 0.15
    likes = random.randint(120, 2400) if big else random.randint(0, 140)
    return {
        "id": str(1850000000000000000 + i * 7919),
        "author_id": uid,
        "text": text,
        "created_at": created.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "lang": lang,
        "public_metrics": {
            "like_count": likes,
            "retweet_count": int(likes * random.uniform(0.05, 0.3)),
            "reply_count": int(likes * random.uniform(0.01, 0.1)),
            "quote_count": int(likes * random.uniform(0.0, 0.05)),
        },
        "entities": {"hashtags": [{"start": 0, "end": 0, "tag": t} for t in tags]},
    }


data = sorted((mk_tweet(i) for i in range(72)), key=lambda t: t["created_at"], reverse=True)
users = [
    {
        "id": uid,
        "username": un,
        "name": name,
        "verified": ver,
        "created_at": "2014-03-0%dT10:00:00.000Z" % (1 + int(uid) % 8),
        "public_metrics": {"followers_count": fol},
    }
    for uid, un, name, fol, ver in USERS
]
payload = {"data": data, "includes": {"users": users}, "meta": {"result_count": len(data)}}
out = Path(__file__).with_name("sample_payload.json")
out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"wrote {out} ({len(data)} tweets, {len(users)} users)")
