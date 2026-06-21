import pathlib
import sys
import time
from decimal import Decimal

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from text2sql import db, llm, orchestrator

CASES = pathlib.Path(__file__).resolve().parent / "cases.yaml"
REPORT = pathlib.Path(__file__).resolve().parent / "report.md"


def norm_cell(c):
    if isinstance(c, (float, Decimal)):
        return f"{round(float(c), 2):.2f}"
    return str(c)


def norm(rows):
    return sorted(tuple(sorted(norm_cell(c) for c in row)) for row in rows)


def matches(predicted, gold):
    return norm(predicted) == norm(gold)


def evaluate():
    cases = yaml.safe_load(CASES.read_text())
    results = []

    for i, case in enumerate(cases, 1):
        _, gold_rows = db.run(case["sql"])
        started = time.perf_counter()
        res = orchestrator.answer(case["question"])
        latency = time.perf_counter() - started

        correct = res["ok"] and matches(res["rows"], gold_rows)
        rejects = sum(1 for s in res["trace"] if not s["verdict"]["ok"])
        results.append({
            "id": i,
            "question": case["question"],
            "correct": correct,
            "attempts": res["attempts"],
            "rejects": rejects,
            "latency": latency,
            "sql": res.get("sql"),
        })
        print(f"[{i:02d}] {'PASS' if correct else 'FAIL'}  "
              f"{res['attempts']} att  {latency:5.1f}s  {case['question']}")

    return results


def report(results):
    total = len(results)
    passed = sum(r["correct"] for r in results)
    first_try = sum(r["correct"] and r["attempts"] == 1 for r in results)
    avg_latency = sum(r["latency"] for r in results) / total
    avg_attempts = sum(r["attempts"] for r in results) / total
    rejects = sum(r["rejects"] for r in results)

    lines = [
        "# Benchmark report",
        "",
        f"- model: `{llm.MODEL}`",
        f"- cases: {total}",
        f"- execution accuracy: **{passed}/{total} ({100 * passed / total:.0f}%)**",
        f"- solved on first attempt: {first_try}/{total}",
        f"- avg latency: {avg_latency:.1f}s",
        f"- avg attempts: {avg_attempts:.2f}",
        f"- queries caught by the reviewer before execution: {rejects}",
        "",
        "| # | result | attempts | latency | question |",
        "|---|--------|----------|---------|----------|",
    ]
    for r in results:
        lines.append(
            f"| {r['id']} | {'pass' if r['correct'] else 'fail'} | "
            f"{r['attempts']} | {r['latency']:.1f}s | {r['question']} |"
        )

    REPORT.write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines[:9]))
    print(f"\nreport written to {REPORT}")


if __name__ == "__main__":
    report(evaluate())
