-- SLOW starter for Q3 (total sessions, 30-min gap).
-- Correct but uses a correlated subquery to find each row's previous timestamp,
-- which is O(n^2)-ish over 120k pageviews. Your job: rewrite with a window
-- function (LAG) so it returns the SAME number far faster.
WITH ordered AS (
    SELECT
        p.user_id,
        p.ts,
        (SELECT MAX(p2.ts)
         FROM pageviews p2
         WHERE p2.user_id = p.user_id
           AND (p2.ts < p.ts OR (p2.ts = p.ts AND p2.view_id < p.view_id))
        ) AS prev_ts
    FROM pageviews p
)
SELECT SUM(
    CASE WHEN prev_ts IS NULL
              OR date_diff('minute', CAST(prev_ts AS TIMESTAMP), CAST(ts AS TIMESTAMP)) > 30
         THEN 1 ELSE 0 END
) AS total_sessions
FROM ordered;
