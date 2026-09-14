# Optimization notes

## Q3: sessions (correlated subquery → `LAG`)

`q3_slow.sql` re-scans `pageviews` for every one of the 120k rows via a
correlated subquery to find each row's previous timestamp for the same user.
`q3.sql` replaces that with `LAG(ts) OVER (PARTITION BY user_id ORDER BY ts,
view_id)`, which computes "previous timestamp per user" in a single windowed
pass over the table (partitioned by `user_id`, with `view_id` only used to
break ties when two pageviews share a timestamp) instead of re-scanning the
table once per outer row. The session count is then a separate, cheap
aggregation over that one column, rather than folding the correlated subquery
and the aggregation into one expensive step.

- `q3_slow.sql`: Total Time 0.168s
- `q3.sql`: Total Time 0.0080s (~21x faster)

Both return the same result: `total_sessions = 118889`.

## Q5: first-touch `/pricing` (correlated subquery → `ROW_NUMBER`)

`q5_slow.sql` uses a correlated subquery to count, for every row, how many
*earlier* pageviews that same user has — effectively a self-join re-run once
per outer row. `q5.sql` replaces that count with
`ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY ts, view_id)`, which ranks
each user's own pageviews by time in a single windowed pass (no extra join).
A user's first-ever pageview is simply the row where that rank is `1`, so the
outer query just filters `earlier_views = 1 AND url_path = '/pricing'` and
counts the matches — no correlated join needed to get there.

- `q5_slow.sql`: Total Time 0.0268s
- `q5.sql`: Total Time 0.0080s (~3.4x faster)

Both return the same result: `users_first_touch_pricing = 412`.
