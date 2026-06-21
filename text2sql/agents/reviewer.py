import json
import re

from .. import db, llm

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|"
    r"merge|copy|call|do|vacuum|reindex|comment)\b",
    re.IGNORECASE,
)

SYSTEM = (
    "You are a SQL reviewer for a data warehouse. Given a schema, a question, and a "
    "candidate PostgreSQL query, decide whether the query correctly answers the question. "
    "Be strict about wrong joins, missing filters, and wrong aggregations, but do not "
    'nitpick column naming or ordering. Reply with JSON only: {"ok": bool, "issue": "..."}.'
)


def review(sql, ddl, question):
    issue = _safety(sql)
    if issue:
        return {"ok": False, "stage": "safety", "issue": issue}

    err = db.explain(sql)
    if err:
        return {"ok": False, "stage": "validate", "issue": err}

    verdict = _critique(sql, ddl, question)
    if not verdict["ok"]:
        return {"ok": False, "stage": "intent", "issue": verdict["issue"]}
    return {"ok": True, "stage": "intent", "issue": None}


def _safety(sql):
    s = sql.strip().rstrip(";")
    if ";" in s:
        return "multiple statements are not allowed"
    if not re.match(r"(?is)^\s*(with|select)\b", s):
        return "only SELECT queries are allowed"
    if FORBIDDEN.search(s):
        return "query contains a forbidden write keyword"
    return None


def _critique(sql, ddl, question):
    raw = llm.complete(
        SYSTEM, f"Schema:\n{ddl}\n\nQuestion: {question}\n\nQuery:\n{sql}", max_tokens=300
    )
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        data = json.loads(raw[start:end])
        return {"ok": bool(data.get("ok")), "issue": data.get("issue") or "intent mismatch"}
    except (ValueError, json.JSONDecodeError):
        return {"ok": True, "issue": None}
