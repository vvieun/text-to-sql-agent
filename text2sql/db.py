import os

import psycopg2

DSN = os.environ.get("DATABASE_URL", "postgresql://dwh:dwh@localhost:5432/dwh")


def connect(read_only=True):
    conn = psycopg2.connect(DSN)
    conn.set_session(readonly=read_only, autocommit=True)
    return conn


def schema_ddl():
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                select table_name, column_name, data_type
                from information_schema.columns
                where table_schema = 'public'
                order by table_name, ordinal_position
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    tables = {}
    for table, column, dtype in rows:
        tables.setdefault(table, []).append(f"{column} {dtype}")
    return "\n".join(f"{t}(" + ", ".join(cols) + ")" for t, cols in tables.items())


def explain(sql):
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute("explain " + sql)
        return None
    except Exception as e:
        return str(e).strip().splitlines()[0]
    finally:
        conn.close()


def run(sql, timeout_ms=5000):
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(f"set statement_timeout = {int(timeout_ms)}")
            cur.execute(sql)
            columns = [d[0] for d in cur.description]
            return columns, cur.fetchall()
    finally:
        conn.close()
