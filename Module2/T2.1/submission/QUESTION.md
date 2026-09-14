# The task

You are given a self-contained synthetic web-analytics dataset for **Larkspur
Media** (no BigQuery, no cloud account — everything is local DuckDB).

- `pageviews.csv` — 120,000 pageviews (view_id, user_id, country, url_path, ts, load_ms)
- `users.csv` — 3,000 users (user_id, plan, country, signup_ts)

Load both into DuckDB and answer the five questions below. **Every answer must
use a window function and/or a CTE** (across the five, at least 4 use a window
function and at least 3 use a CTE).

Put each answer in its own file: `submission/q1.sql` … `submission/q5.sql`. Each
file must be a single `SELECT` returning exactly the columns specified.

| # | Question | Output columns |
|---|---|---|
| q1 | For each country, the single most-viewed `url_path` (ties broken by path A→Z). | `country, url_path, views` |
| q2 | 7-day moving average of daily total pageviews, for March 2025 only. | `day, views, mov_avg_7d` (rounded 2dp) |
| q3 | Total number of sessions across all users, where a gap > 30 min between a user's consecutive pageviews starts a new session. | `total_sessions` |
| q4 | Median `load_ms` per plan. | `plan, median_load_ms` (rounded 1dp) |
| q5 | Number of users whose **first-ever** pageview was `/pricing`. | `users_first_touch_pricing` |

## The optimization part

`data/starter/q3_slow.sql` and `data/starter/q5_slow.sql` are **correct but slow**
— each uses a correlated subquery over all 120k rows. Your `q3.sql` and `q5.sql`
must return the identical result **and run measurably faster** (the grader
measures the speedup against these starters). For each, write one sentence in
`submission/OPTIMIZATION.md` explaining *why* your rewrite is cheaper.

## Deterministic grading

An automated grader checks: (1) all 5 answers match the expected results, (2) the
window/CTE construct requirement, (3) q3/q5 reproduce the expected answer and clear the speedup
bar vs the slow starters.