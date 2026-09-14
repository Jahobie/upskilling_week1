What you need to do
You are given four CSV files from a retailer and one question from an executive. Answer it using SQL alone, then explain the answer in a one-page memo a non-technical CFO can act on.

All data is provided (a made-up retailer, 'Meridian Outfitters'): four CSV files and the question in QUESTION.md. Load them into DuckDB and answer using SQL only — no Python/pandas. Submit your query, your answer, and a one-page memo for a non-technical CFO. Watch out: the product category that sells the most isn't the one that earns the most once refunds are counted, so a quick answer will be wrong. The grader re-runs your SQL to confirm your answer is real.

Your submission ZIP must use this exact structure, with paths relative to the ZIP root:

```text
submission/
  solution.sql
  answer.json
  MEMO.md
```

`answer.json` must use this shape:

```json
{
  "category": "your answer",
  "net_revenue_usd": 12345.67
}
```

The memo must contain no more than roughly 500 words, state the conclusion in its first sentence, and include exactly one chart. Represent the chart as one Markdown image, one HTML `<img>`, or one fenced `text`/`ascii` chart block so the evaluator can count it consistently.
Task files

Everything you need is bundled here — no external accounts or datasets required.

    QUESTION.md

    The business question and submission spec.
    customers.csv

    220 synthetic customers (id, name, region, signup_date).
    products.csv

    Product catalog (id, name, category, unit_price).
    orders.csv

    2,600 orders across 2025 (order_id, customer_id, product_id, quantity, order_date, status).
    refunds.csv

    Refunds issued against orders (refund_id, order_id, amount, refund_date).

Expected submission ZIP structure

Put the following files at these exact paths inside your submission ZIP. Extra files and folders are okay.

submission.zip/
└── submission/
    ├── solution.sql  # SQL analysis
    ├── answer.json  # machine-readable answer
    └── MEMO.md  # executive memo

** means any nested folders and * means any matching filename. When several paths say “choose one,” include one of those alternatives.
Definition of ‘done’

Your submission is ready when all of the following are true:

    Your answer (the category and the figure) is correct, and your SQL actually produces it
    No Python or pandas used for the analysis — SQL only
    The memo is one page, leads with the answer in the first sentence, and has exactly one chart
    Someone with no SQL background can read it cold and tell you the answer and the catch