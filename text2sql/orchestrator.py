from typing import Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from . import db
from .agents import generator, reviewer, schema_agent
from .tracing import flush, observe


class State(TypedDict, total=False):
    question: str
    max_attempts: int
    ddl: str
    sql: str
    verdict: dict
    feedback: Optional[str]
    columns: list
    rows: list
    attempts: int
    trace: list
    ok: bool


@observe(name="schema")
def schema_node(state):
    return {"ddl": schema_agent.select(state["question"])}


@observe(name="generate")
def generate_node(state):
    sql = generator.write(state["question"], state["ddl"], state.get("feedback"))
    attempt = state.get("attempts", 0) + 1
    return {"sql": sql, "attempts": attempt, "trace": state["trace"] + [{"attempt": attempt, "sql": sql}]}


@observe(name="review")
def review_node(state):
    verdict = reviewer.review(state["sql"], state["ddl"], state["question"])
    state["trace"][-1]["verdict"] = verdict
    feedback = None if verdict["ok"] else f"{verdict['stage']}: {verdict['issue']}"
    return {"verdict": verdict, "feedback": feedback, "trace": state["trace"]}


@observe(name="execute")
def execute_node(state):
    try:
        columns, rows = db.run(state["sql"])
        return {"columns": columns, "rows": rows, "ok": True}
    except Exception as e:
        msg = str(e).strip().splitlines()[0]
        state["trace"][-1]["error"] = msg
        return {"feedback": f"execution error: {msg}", "trace": state["trace"], "ok": False}


def after_review(state):
    if state["verdict"]["ok"]:
        return "execute"
    return "generate" if state["attempts"] < state["max_attempts"] else END


def after_execute(state):
    if state.get("ok"):
        return END
    return "generate" if state["attempts"] < state["max_attempts"] else END


def _build():
    g = StateGraph(State)
    g.add_node("schema", schema_node)
    g.add_node("generate", generate_node)
    g.add_node("review", review_node)
    g.add_node("execute", execute_node)
    g.add_edge(START, "schema")
    g.add_edge("schema", "generate")
    g.add_edge("generate", "review")
    g.add_conditional_edges("review", after_review, ["execute", "generate", END])
    g.add_conditional_edges("execute", after_execute, ["generate", END])
    return g.compile()


GRAPH = _build()


@observe(name="answer")
def answer(question, max_attempts=3):
    final = GRAPH.invoke(
        {"question": question, "max_attempts": max_attempts, "attempts": 0, "trace": [], "ok": False}
    )
    flush()
    result = {"ok": final.get("ok", False), "attempts": final.get("attempts", 0), "trace": final["trace"]}
    if result["ok"]:
        result.update(sql=final["sql"], columns=final["columns"], rows=final["rows"])
    return result
