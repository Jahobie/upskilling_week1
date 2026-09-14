WITH staged AS (
      SELECT
          user_id, view_id, ts,
          LAG(ts) OVER (PARTITION BY user_id ORDER BY ts, view_id) AS ordered
      FROM pageviews p
  )
SELECT
      SUM(CASE WHEN ordered IS NULL OR  date_diff('minute', CAST(ordered AS TIMESTAMP), CAST(ts AS TIMESTAMP)) > 30 THEN 1 ELSE 0 END) AS total_sessions
FROM staged;
