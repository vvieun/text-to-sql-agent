[English](README.md) · [Русский](README.ru.md)

# text-to-sql-agent

A team of agents turns a question in plain language into a SQL query. The query runs over a data warehouse (postgresql, star schema) in read-only mode.

The agents are run by a state graph built on langgraph. The graph has a self-correction loop. Each run is traced in langfuse.

## Table of contents

- [Architecture](#architecture)
- [Stack](#stack)
- [Data](#data)
- [Example run](#example-run)
- [Benchmarks](#benchmarks)
- [Security](#security)
- [Tracing](#tracing)
- [Configuration](#configuration)
- [Notes](#notes)

## Architecture

### Agent interaction sequence diagram

![sequence](docs/sequence.en.png)

Agents:
- **schema agent** (`text2sql/agents/schema_agent.py`) picks only the tables that the question needs;
- **generator** (`text2sql/agents/generator.py`) writes one select and rewrites it when it gets feedback;
- **reviewer** (`text2sql/agents/reviewer.py`) does three checks: a safety check (select only, one statement, no write keywords), a check with `explain`, and an llm check that asks "does the query answer the question";
- **executor** (`db.run`) runs the query in a `read only` postgres session with a timeout.

### Graph in `text2sql/orchestrator.py`

The nodes are agents. Conditional edges make the loop (dashed lines mean conditional steps).

![state graph](docs/graph.png)

## Stack

python, postgresql, anthropic api, langgraph, langfuse.

## Data

**Star schema:** fact `fact_sales` + dimensions `dim_date`, `dim_customer`, `dim_product`, `dim_store`.

Filled with fake data (`text2sql/seed.py`).

## Example run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # вписать anthropic_api_key

docker compose up -d          
python -m text2sql.seed       
python -m text2sql.cli "выручка по категориям товаров за 2024"
```

The trace shows every attempt, the queries the reviewer turned down, and the final result.

## Benchmarks

```bash
python -m benchmark.run
```

Runs the agent over pairs (question and reference sql) from `benchmark/cases.yaml`. It then computes:

- the agent's result against the reference (compared as multisets, ignoring order and column names);
- the share solved on the first attempt;
- average latency and number of attempts;
- how many queries the reviewer turned down before execution.

The report is saved to `benchmark/report.md`.

### Example report:

- model: `claude-opus-4-8`
- cases: 12
- execution accuracy: **11/12 (92%)**
- solved on first attempt: 9/12
- avg latency: 3.3s
- avg attempts: 1.33
- queries caught by the reviewer before execution: 2

| # | result | attempts | latency | question |
|---|--------|----------|---------|----------|
| 1 | pass | 1 | 2.0s | What is the total revenue across all sales? |
| 2 | pass | 1 | 2.3s | Show total revenue per product category. |
| 3 | pass | 1 | 2.6s | Who are the top 5 customers by total revenue? |
|...|||||

## Security

Two separate layers:
1. **static check** removes anything that is not a single select, and any write keywords (`insert`, `update`, `delete`, `drop`, …);
2. **database level**, where the executor runs in a `read only` session.

## Tracing

Every graph step and llm call is wrapped in langfuse (`@observe`, `text2sql/tracing.py`):
- with the `langfuse_public_key` / `langfuse_secret_key` keys, a run is shown as a tree: trace `answer` - one span per graph node (`schema`, `generate`, `review`, `execute`) - a generation with model, tokens, and latency;
- without the keys, tracing does nothing and gets out of the way.

## Configuration

| variable | default |
|------------|--------------|
| `anthropic_api_key` | — |
| `database_url` | `postgresql://dwh:dwh@localhost:5432/dwh` |
| `dwh_agent_model` | `claude-opus-4-8` |
| `langfuse_public_key` / `langfuse_secret_key` | not set |
| `langfuse_base_url` | `https://cloud.langfuse.com` |

## Notes

The result comparison rounds cell numbers and ignores column order. Because of this, it can sometimes treat two results with different shapes as the same. For a stricter check, you can set the expected columns in the case.
