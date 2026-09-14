# Companies turn raw data into trustworthy tables using pipelines that run on a schedule and recover when something fails. Knowing the standard tools (dbt plus a scheduler) makes you useful on a data team right away.
What you need to do
You are given raw customers, orders, and payments tables. Build a dbt pipeline that turns them into one tested customer_orders table, and run it on a schedule that recovers on its own when a step fails.

Seed data is provided (customers, orders, payments). Build a dbt project that transforms it into a final table (`customer_orders`) matching the spec in QUESTION.md. Add data-quality tests, a freshness check, and make one model 'incremental' (it only processes new rows, so re-runs are faster). Then run it on a schedule with Airflow or Dagster in Docker, including one task that fails on purpose the first time and is automatically retried. Export your final table to `customer_orders.csv` so the grader can check it against the correct output.

Use `order_date` as the incremental boundary. To demonstrate correctness, first build with orders through `2025-03-31`, then add the remaining supplied orders and run incrementally; the result must equal a full refresh over all supplied rows. Configure source freshness on orders using `order_date`; because the fixture is historical, the grader checks that the freshness configuration exists rather than requiring a wall-clock freshness pass. The deliberately flaky orchestrator task must fail exactly once on a fresh run and succeed on its first retry. Compare the incremental run with a full refresh on the same machine and report both timings; timing is evidence, not a cross-machine pass/fail threshold.
Task files

# Everything you need is bundled here — no external accounts or datasets required.

    QUESTION.md

    Required models, tests, incremental model, freshness, and orchestrator retry spec.
    raw_customers.csv

    400 customers.
    raw_orders.csv

    5,000 orders (order_id, customer_id, order_date, status).
    raw_payments.csv

    3,376 payments (payment_id, order_id, amount, method).

# Expected submission ZIP structure

Put the following files at these exact paths inside your submission ZIP. Extra files and folders are okay.

submission.zip/
└── submission/
    ├── dbt_project.yml  # dbt project configuration
    ├── models/
    │   └── **/
    │       └── *.sql  # dbt models
    ├── customer_orders.csv  # exported final table
    ├── orchestrator_log.txt  # orchestrator retry log
    └── NOTES.md  # incremental timing and design notes

** means any nested folders and * means any matching filename. When several paths say “choose one,” include one of those alternatives.
Definition of ‘done’

Your submission is ready when all of the following are true:

    Your customer_orders table matches the required spec exactly
    dbt tests pass
    One model is incremental, produces the same result as a full refresh after the staged-data test, and includes same-machine timing evidence
    Your orchestrator log shows the flaky task fail, retry, then succeed