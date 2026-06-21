import json

from .. import db, llm

SYSTEM = (
    "You are a data warehouse schema retriever. Given a question and a list of table "
    "names from a star schema, return the minimal set of tables needed to answer it. "
    'Reply with JSON only: {"tables": ["..."]}.'
)


def select(question):
    full = db.schema_ddl()
    names = [line.split("(", 1)[0] for line in full.splitlines()]

    raw = llm.complete(SYSTEM, f"Tables: {names}\nQuestion: {question}", max_tokens=200)
    chosen = _parse(raw, names)

    keep = [n for n in chosen if n in names] or names
    return "\n".join(line for line in full.splitlines() if line.split("(", 1)[0] in keep)


def _parse(raw, names):
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        return json.loads(raw[start:end]).get("tables", [])
    except (ValueError, json.JSONDecodeError):
        return names
