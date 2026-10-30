-- Q1: one row per eligible agent per calendar day, including zero activity.
-- Inactive agents are included through October 19; joining day is inclusive.
-- Each statement is independently executable against the eight source tables.
-- result: q1_agent_day
WITH RECURSIVE calendar(day) AS (
    SELECT '2026-10-13'
    UNION ALL SELECT date(day, '+1 day') FROM calendar WHERE day < '2026-10-26'
), eligible AS (
    SELECT a.*, c.day, CASE WHEN c.day < '2026-10-20' THEN 1 ELSE 2 END AS week
    FROM agents a CROSS JOIN calendar c
    WHERE a.joining_date <= c.day
      AND (a.active_status = 'Active' OR c.day <= '2026-10-19')
), events AS (
    SELECT agent_id, date(event_time) AS day,
           SUM(status = 'Assigned') AS attempts, SUM(status = 'Delivered') AS delivered,
           SUM(status = 'Hold') AS holds, SUM(status = 'Returned') AS returned
    FROM order_logs
    WHERE event_time >= '2026-10-13' AND event_time < '2026-10-27'
    GROUP BY agent_id, date(event_time)
), daily AS (
    SELECT e.*, COALESCE(v.attempts, 0) AS attempts, COALESCE(v.delivered, 0) AS delivered,
           COALESCE(v.holds, 0) AS holds, COALESCE(v.returned, 0) AS returned
    FROM eligible e LEFT JOIN events v ON e.agent_id = v.agent_id AND e.day = v.day
)
SELECT d.day, d.week, d.agent_id, d.agent_name, h.hub_id, h.hub_name,
       d.salary_type, d.attempts, d.delivered, d.holds, d.returned
FROM daily d JOIN hubs h ON h.hub_id = d.hub_id
ORDER BY d.day, h.hub_id, d.agent_id;

-- result: q1_hub_summary
WITH RECURSIVE calendar(day) AS (
    SELECT '2026-10-13'
    UNION ALL SELECT date(day, '+1 day') FROM calendar WHERE day < '2026-10-26'
), eligible AS (
    SELECT a.*, c.day, CASE WHEN c.day < '2026-10-20' THEN 1 ELSE 2 END AS week
    FROM agents a CROSS JOIN calendar c
    WHERE a.joining_date <= c.day
      AND (a.active_status = 'Active' OR c.day <= '2026-10-19')
), events AS (
    SELECT agent_id, date(event_time) AS day,
           SUM(status = 'Assigned') AS attempts, SUM(status = 'Delivered') AS delivered,
           SUM(status = 'Hold') AS holds, SUM(status = 'Returned') AS returned
    FROM order_logs
    WHERE event_time >= '2026-10-13' AND event_time < '2026-10-27'
    GROUP BY agent_id, date(event_time)
), daily AS (
    SELECT e.*, COALESCE(v.attempts, 0) AS attempts, COALESCE(v.delivered, 0) AS delivered,
           COALESCE(v.holds, 0) AS holds, COALESCE(v.returned, 0) AS returned
    FROM eligible e LEFT JOIN events v ON e.agent_id = v.agent_id AND e.day = v.day
)
SELECT h.hub_id, h.hub_name, COUNT(d.agent_id) AS available_agent_days,
       COALESCE(SUM(d.delivered), 0) AS delivered,
       1.0 * SUM(d.delivered) / NULLIF(COUNT(d.agent_id), 0) AS avg_deliveries_per_agent_day
FROM hubs h LEFT JOIN daily d ON h.hub_id = d.hub_id
GROUP BY h.hub_id, h.hub_name ORDER BY h.hub_id;
