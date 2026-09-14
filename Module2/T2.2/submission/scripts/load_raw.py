"""One-time loader: creates raw_* tables in Postgres and loads the CSVs.

Orders are loaded in two phases so we can demonstrate the incremental
model: run with --phase initial first (orders through 2025-03-31), then
--phase append to add the rest.
"""
import argparse
import csv
import io
import os

import psycopg2

CONN_KWARGS = dict(host="localhost", port=5432, user="dbt", password="dbt", dbname="dbt")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DDL = {
    "raw_customers": """
        CREATE TABLE IF NOT EXISTS raw_customers (
            customer_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            signup_date DATE
        )
    """,
    "raw_orders": """
        CREATE TABLE IF NOT EXISTS raw_orders (
            order_id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            order_date DATE,
            status TEXT
        )
    """,
    "raw_payments": """
        CREATE TABLE IF NOT EXISTS raw_payments (
            payment_id INTEGER PRIMARY KEY,
            order_id INTEGER,
            amount NUMERIC,
            method TEXT
        )
    """,
}

CUTOFF = "2025-03-31"


def copy_csv(cur, table, rows_iter, header):
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows_iter:
        writer.writerow(row)
    buf.seek(0)
    cols = ",".join(header)
    cur.copy_expert(f"COPY {table} ({cols}) FROM STDIN WITH CSV", buf)


def load_full(cur, table, filename):
    path = os.path.join(HERE, filename)
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        copy_csv(cur, table, reader, header)


def load_orders_initial(cur):
    path = os.path.join(HERE, "raw_orders.csv")
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        date_idx = header.index("order_date")
        rows = [r for r in reader if r[date_idx] <= CUTOFF]
    copy_csv(cur, "raw_orders", rows, header)
    return len(rows)


def load_orders_append(cur):
    path = os.path.join(HERE, "raw_orders.csv")
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        date_idx = header.index("order_date")
        rows = [r for r in reader if r[date_idx] > CUTOFF]
    copy_csv(cur, "raw_orders", rows, header)
    return len(rows)


def load_orders_full(cur):
    load_full(cur, "raw_orders.csv", "raw_orders")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["initial", "append", "full", "reset"], required=True)
    args = parser.parse_args()

    conn = psycopg2.connect(**CONN_KWARGS)
    conn.autocommit = True
    cur = conn.cursor()

    if args.phase == "reset":
        for t in ("raw_customers", "raw_orders", "raw_payments"):
            cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
        print("Dropped raw tables.")
        return

    for t, ddl in DDL.items():
        cur.execute(ddl)

    if args.phase == "initial":
        cur.execute("TRUNCATE raw_customers, raw_orders, raw_payments")
        load_full(cur, "raw_customers", "raw_customers.csv")
        load_full(cur, "raw_payments", "raw_payments.csv")
        n = load_orders_initial(cur)
        print(f"Loaded raw_customers, raw_payments (full) and raw_orders (initial, {n} rows through {CUTOFF}).")
    elif args.phase == "append":
        n = load_orders_append(cur)
        print(f"Appended {n} raw_orders rows after {CUTOFF}.")
    elif args.phase == "full":
        cur.execute("TRUNCATE raw_customers, raw_orders, raw_payments")
        load_full(cur, "raw_customers", "raw_customers.csv")
        load_full(cur, "raw_payments", "raw_payments.csv")
        cur.execute("COPY raw_orders FROM STDIN WITH CSV") if False else None
        with open(os.path.join(HERE, "raw_orders.csv"), newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            rows = list(reader)
        copy_csv(cur, "raw_orders", rows, header)
        print("Loaded all three raw tables in full.")

    for t in ("raw_customers", "raw_orders", "raw_payments"):
        cur.execute(f"SELECT count(*) FROM {t}")
        print(t, cur.fetchone()[0])

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
