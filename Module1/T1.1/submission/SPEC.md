# Ship an Integration — No Agent (self-contained)

A customer sends a messy vendor transactions file, `messy_transactions.csv`
(60 rows: `row_id, date, merchant, amount, currency`). Build a **production CLI**
(no agent) that normalizes it and reports invalid rows. Treat it as a customer
deliverable: tests, `mypy --strict`, structured JSON logs, retries, clean CLI.

## Exact normalization rules (so the output is well-defined)

For each row, produce a **clean** record or an **error**:

- **date** → ISO `YYYY-MM-DD`. Accept `YYYY-MM-DD`, `MM/DD/YYYY`, and `Mon DD, YYYY`
  (e.g. `Mar 14, 2025`). If none parse → error `unparseable_date`.
- **amount** → integer `amount_cents`. Strip `$`, commas, spaces. `(...)` around the
  value means a **refund** → negative cents. `N/A`/empty/unparseable → error
  `unparseable_amount`.
- **currency** → trim; empty → `USD`; uppercase; a bare `$` means `USD`.
- **merchant** → trim and collapse internal whitespace to single spaces.

A row is an **error** if its date or amount can't be parsed (report `row_id` +
`reason`); otherwise it's **clean**.

## Contract for grading

Your tool must run as:

```bash
bash submission/run.sh <input_csv> <output_json>
```

and write `{ "clean": [ {row_id, date, merchant, amount_cents, currency}, ... ],
"errors": [ {row_id, reason}, ... ] }`. Also emit `submission/run.log` as JSON
lines, each with a `correlation_id`.

## Grading

An automated grader runs your tool on `messy_transactions.csv`, compares clean + error
rows to the expected output, and validates the structured log. `mypy
--strict` and `pytest --cov` run against your repo. README trade-offs are judged
separately.
