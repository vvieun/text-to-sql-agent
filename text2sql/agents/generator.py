from .. import llm

SYSTEM = (
    "You are a senior analytics engineer writing PostgreSQL for a star-schema warehouse. "
    "Write a single read-only SELECT query that answers the question. "
    "Use only the tables and columns provided. Prefer explicit JOINs and clear aliases. "
    "Return the SQL only, with no markdown fences and no explanation."
)


def write(question, ddl, feedback=None):
    parts = [f"Schema:\n{ddl}", f"Question: {question}"]
    if feedback:
        parts.append(f"Your previous attempt failed. Fix it. Feedback: {feedback}")
    return _clean(llm.complete(SYSTEM, "\n\n".join(parts)))


def _clean(sql):
    sql = sql.strip()
    if sql.startswith("```"):
        sql = sql.split("```", 2)[1]
        if sql.lower().startswith("sql"):
            sql = sql[3:]
    return sql.strip().rstrip(";").strip()
