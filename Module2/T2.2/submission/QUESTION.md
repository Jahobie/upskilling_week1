# The task

Fully self-contained seed data is provided (no BigQuery, no external warehouse):

- `raw_customers.csv` (400), `raw_orders.csv` (5,000), `raw_payments.csv` (3,376)

Build a **dbt project** (DuckDB or Postgres adapter — both run locally) with:

1. **Staging models** for the three sources.
2. A **marts** model `customer_orders` with exactly these columns:
   `customer_id, customer_name, n_orders, total_amount, first_order_date,
   most_recent_order_date`, where an "order" counts only if its status is
   `completed` or `shipped`, `total_amount` sums that order's payments, and
   customers with zero qualifying orders are excluded.
3. At least one model materialized **`incremental`**, and it must be
   demonstrably faster on re-run than a full refresh.
4. **dbt tests** (e.g. `unique`, `not_null`, relationships) that pass.
5. A **source freshness** config.
6. The whole thing wired into **Airflow or Dagster** (in Docker), including one
   deliberately **flaky task** that fails once and is **retried** to success.

## What to submit

- Your dbt project (in the repo).
- `submission/customer_orders.csv` — your built mart exported to CSV. **This is
  the deterministic check** — it must match the expected table exactly.
- `submission/orchestrator_log.txt` — orchestrator output showing the flaky task
  fail → retry → succeed.
- `submission/NOTES.md` — how you made the model incremental, and the re-run
  timing before/after.

## Grading

An automated grader checks the mart against the expected output (deterministic), the incremental
materialization and freshness config (if you point it at your dbt project), and
the retry evidence in the log.
