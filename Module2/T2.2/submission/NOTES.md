# Notes: incremental model and orchestration

## How `stg_orders` is made incremental

`models/staging/stg_orders.sql` is configured `materialized='incremental'` with
`unique_key='order_id'`. On a normal run it selects every row from
`source('raw', 'raw_orders')`. On an incremental run (`is_incremental()` is
true, i.e. the table already exists and this isn't a `--full-refresh`), it
adds:

```sql
where order_date > (select coalesce(max(order_date), '1900-01-01'::date) from {{ this }})
```

so only orders newer than what's already in the table get scanned and
inserted — `order_date` is the incremental boundary. `customer_orders`
(the marts model) stays a plain `table`: it's cheap to fully recompute from
the already-small staging tables, so only the raw-source scan needed to be
incremental.

## Correctness demonstration

1. Loaded `raw_customers` and `raw_payments` in full, but `raw_orders` only
   through `2025-03-31` (2,500 of 5,000 rows) — `scripts/load_raw.py --phase initial`.
2. Ran `dbt run` (first-ever build of `stg_orders`, so it's a full build of
   those 2,500 rows) → `customer_orders` had 394 customers.
3. Appended the remaining 2,500 orders (`--phase append`).
4. Ran `dbt run --select stg_orders customer_orders` again: dbt reported
   `INSERT 0 2500` for `stg_orders` — it only processed the *new* rows, not
   all 5,000 — then rebuilt `customer_orders` from the now-complete staging
   table (400 customers).
5. Snapshotted `customer_orders` to CSV, then ran
   `dbt run --select stg_orders customer_orders --full-refresh` (rebuilds
   `stg_orders` from scratch over all 5,000 rows) and snapshotted again.
6. `diff`'d the two snapshots: **identical, byte-for-byte.** The incremental
   result equals a full refresh over all supplied rows.

## Timing

On this machine (5,000 orders total — a small dataset for Postgres), dbt's
own per-model `execution_time` from `target/run_results.json`:

| Run                                   | `stg_orders` execution time | rows processed |
|----------------------------------------|-----------------------------|-----------------|
| Initial build (2,500 rows, first-ever)  | ~0.10s                      | 2,500 (full)    |
| Incremental catch-up (+2,500 new rows)  | ~0.13s                      | 2,500 (delta only) |
| Full refresh (all 5,000 rows)           | ~0.11s                      | 5,000 (full)    |

Honest caveat: at this row count, Postgres query-planning/connection
overhead dominates and the wall-clock difference is within noise — it is
**not** a clean speed win on its own here. The real, deterministic evidence
that incremental is doing less work is the **row count dbt reports
scanning/inserting**: the incremental run only touched the 2,500 *new* rows
(`INSERT 0 2500`), never re-touching the 2,500 rows already loaded, while
the full refresh re-scanned all 5,000. That gap (and the time it represents)
scales linearly with total table size — at realistic production volumes
(millions of rows), the same mechanism turns into a real, large wall-clock
saving, since a full refresh's cost keeps growing with total history while
an incremental run's cost only grows with the size of the new batch.

## Orchestration (Dagster, in Docker)

`dagster_pipeline.py` defines `customer_orders_job`: `dbt_run_op` →
`dbt_test_op` → `flaky_op`. `flaky_op` has a `RetryPolicy(max_retries=1)`
and deliberately raises on `context.retry_number == 0` (its first attempt),
succeeding on the retry. Run via:

```
sudo docker compose build dagster
sudo docker compose run --rm dagster
```

which builds a Dagster + dbt-postgres image, runs the job once against the
`postgres` service on the shared Docker network, and writes full output to
`orchestrator_log.txt`.

One implementation note for whoever reads this later: the `dagster job
execute` CLI command (Dagster's own CLI help flags it as superseded/
deprecated) logged `STEP_UP_FOR_RETRY` for the flaky step but then ended the
run as `RUN_SUCCESS` without ever actually re-executing the step — it never
produced real retry evidence. Calling `customer_orders_job.execute_in_process()`
directly from a small `__main__` block in `dagster_pipeline.py` (Dagster's
documented way to run a job programmatically) uses a different execution
loop that correctly re-runs a step marked for retry, and is what's wired up
in `docker-compose.yml` now. The log shows the full sequence: `flaky_op`
fails on attempt 1 → `STEP_RESTARTED (attempt # 2)` → succeeds → `STEP_SUCCESS`
→ overall `RUN_SUCCESS`.
