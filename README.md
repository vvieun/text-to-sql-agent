# text-to-sql-agent

Мульти-агентный перевод вопроса на естественном языке в sql запрос над хранилищем данных (postgresql, звёздная схема) и выполнение в режиме read-only. 

Оркестрация - граф состояний на langgraph с циклом самокоррекции, каждый запуск трейсится в langfuse.

## Содержание

- [Архитектура](#архитектура)
- [Стек](#стек)
- [Данные](#данные)
- [Пример запуска](#пример-запуска)
- [Измерения](#измерения)
- [Безопасность](#безопасность)
- [Трейсинг](#трейсинг)
- [Конфигурация](#конфигурация)
- [Заметки](#заметки)

## Архитектура

### Диаграмма последовательностей взаимодействия агентов

![sequence](docs/sequence.png)

Агенты:
- **schema agent** (`text2sql/agents/schema_agent.py`) сужает схему до таблиц, нужных под вопрос;
- **generator** (`text2sql/agents/generator.py`) пишет один select и переписывает его по фидбэку;
- **reviewer** (`text2sql/agents/reviewer.py`) выполняет три проверки: статическая безопасность (только select, одно выражение, без write-ключевых слов), валидация через `explain`, llm-критика «отвечает ли запрос на вопрос»;
- **executor** (`db.run`) отправляет запрос в `read only` сессии postgres с таймаутом.

### Граф в `text2sql/orchestrator.py` 
узлами являются агенты, условные рёбра задают цикл (пунктир — условные переходы)


![граф состояний](docs/graph.png)

## Стек

python, postgresql, anthropic api, langgraph, langfuse.

## Данные

**Звёздная схема:** факт `fact_sales` + измерения `dim_date`, `dim_customer`, `dim_product`, `dim_store`. 

Наполняется синтетикой (`text2sql/seed.py`).

## Пример запуска

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # вписать anthropic_api_key

docker compose up -d          
python -m text2sql.seed       
python -m text2sql.cli "выручка по категориям товаров за 2024"
```

Трейс показывает каждую попытку, отклонения reviewer и итоговый результат.

## Измерения

```bash
python -m benchmark.run
```

Гоняет агента по парам (вопрос и эталонный sql) из `benchmark/cases.yaml` и считает:

- результат агента против эталона (сравнение как мультимножеств, без учёта порядка и имён колонок);
- доля решённых с первой попытки;
- средняя латентность и число попыток;
- сколько запросов reviewer отклонил до выполнения.

Отчёт пишется в `benchmark/report.md`. 

### Пример отчета:

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

## Безопасность

Два независимых слоя:
1. **статическая проверка** режет всё, что не является одиночным select, и любые write-ключевые слова (`insert`, `update`, `delete`, `drop`, …);
2. **уровень бд**, на котором executor работает в `read only` сессии.

## Трейсинг

Каждый шаг графа и вызов llm обёрнут в langfuse (`@observe`, `text2sql/tracing.py`):
- c ключами `langfuse_public_key` / `langfuse_secret_key` запуск виден деревом: трейс `answer` - спан на узел графа (`schema`, `generate`, `review`, `execute`) - generation с моделью, токенами и латентностью;
- без ключей трейсинг - прозрачный no-op.

## Конфигурация

| переменная | по умолчанию |
|------------|--------------|
| `anthropic_api_key` | — |
| `database_url` | `postgresql://dwh:dwh@localhost:5432/dwh` |
| `dwh_agent_model` | `claude-opus-4-8` |
| `langfuse_public_key` / `langfuse_secret_key` | не заданы |
| `langfuse_base_url` | `https://cloud.langfuse.com` |

## Заметки

Сравнение результатов нормализует значения ячеек (округляет числа) и игнорирует порядок колонок, а значит изредка может счесть два разных по форме результата одинаковыми. Для более строгой оценки можно зафиксировать ожидаемые колонки в кейсе.
