import sys

from . import orchestrator


def render(columns, rows, limit=20):
    widths = [len(c) for c in columns]
    shown = rows[:limit]
    for r in shown:
        widths = [max(w, len(str(v))) for w, v in zip(widths, r)]
    line = lambda cells: " | ".join(str(v).ljust(w) for v, w in zip(cells, widths))
    out = [line(columns), "-+-".join("-" * w for w in widths)]
    out += [line(r) for r in shown]
    if len(rows) > limit:
        out.append(f"... {len(rows) - limit} more rows")
    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        print('usage: python -m text2sql.cli "your question"')
        return

    question = " ".join(sys.argv[1:])
    result = orchestrator.answer(question)

    for step in result["trace"]:
        v = step["verdict"]
        flag = "ok" if v["ok"] else f"rejected ({v['stage']}: {v['issue']})"
        print(f"[attempt {step['attempt']}] {flag}")
        print(step["sql"])
        if step.get("error"):
            print(f"  -> execution error: {step['error']}")
        print()

    if result["ok"]:
        print(f"answered in {result['attempts']} attempt(s):\n")
        print(render(result["columns"], result["rows"]))
    else:
        print(f"failed after {result['attempts']} attempts")


if __name__ == "__main__":
    main()
