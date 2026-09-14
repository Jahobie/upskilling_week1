# The question

You are a Forward Deployed Engineer embedded with **Meridian Outfitters**, a
direct-to-consumer outdoor retailer. Their CFO is preparing for a board meeting
and needs one number, defensibly derived.

> **For fiscal Q3 2025 (July 1 – September 30, 2025), which product category
> generated the highest _net revenue_, and what was that figure (USD)?**
>
> Net revenue = gross merchandise value of **completed** orders in the quarter,
> **minus refunds** issued against those orders.

Notes that matter:

- Only orders with `status = 'completed'` count toward revenue. `cancelled` and
  `pending` orders do not.
- "In the quarter" is defined by `order_date`. A refund counts against a category
  only if the order it refunds is a completed Q3 order.
- The CFO has been burned before by "gross" numbers that ignored returns. The
  category that sells the most is not necessarily the one that earns the most.

## What to submit

1. `submission/solution.sql` — the DuckDB SQL that produces your answer. **No
   Python/pandas analytics** — the computation must happen in SQL.
2. `submission/answer.json`:
   ```json
   { "category": "<your answer>", "net_revenue_usd": <number> }
   ```
3. `submission/MEMO.md` — a ≤1-page memo for the (non-technical) CFO. Lead with
   the answer in the first sentence. Exactly one chart. No SQL jargon.
