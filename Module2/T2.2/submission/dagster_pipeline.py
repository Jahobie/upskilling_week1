"""Dagster job that builds the dbt project and demonstrates a retried task.

dbt_run_op -> dbt_test_op -> flaky_op

flaky_op deliberately fails on its first attempt of every run and succeeds
on the automatic retry, per its RetryPolicy.
"""
import os
import subprocess

from dagster import In, Nothing, Out, OpExecutionContext, RetryPolicy, in_process_executor, job, op

DBT_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


def _run_dbt(context: OpExecutionContext, *args: str) -> None:
    cmd = ["dbt", *args, "--project-dir", DBT_PROJECT_DIR, "--profiles-dir", DBT_PROJECT_DIR]
    context.log.info("Running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


@op(out=Out(Nothing))
def dbt_run_op(context: OpExecutionContext):
    _run_dbt(context, "run")


@op(ins={"start": In(Nothing)}, out=Out(Nothing))
def dbt_test_op(context: OpExecutionContext):
    _run_dbt(context, "test")


@op(ins={"start": In(Nothing)}, retry_policy=RetryPolicy(max_retries=1, delay=2))
def flaky_op(context: OpExecutionContext):
    if context.retry_number == 0:
        raise Exception("Simulated transient failure on first attempt")
    context.log.info(f"flaky_op succeeded on retry {context.retry_number}")


@job(executor_def=in_process_executor)
def customer_orders_job():
    flaky_op(start=dbt_test_op(start=dbt_run_op()))


if __name__ == "__main__":
    result = customer_orders_job.execute_in_process()
    print(f"\nJob result: {'SUCCESS' if result.success else 'FAILURE'}")
