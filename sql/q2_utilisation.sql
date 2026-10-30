-- Q2: Assigned events / (eligible agent-days * standard 40 attempts/day).
-- Eligibility includes joining dates, zero-activity days, and Week 1 departures.
-- Breach uses strictly greater than the 85% target, with a separate Week 2 flag.
-- result: q2_utilisation
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
), weeks(week) AS (VALUES (1), (2)), parameters AS (
    SELECT CAST((SELECT value FROM rules WHERE rule = 'Standard attempts per agent per day') AS REAL) AS standard,
           CAST((SELECT value FROM rules WHERE rule = 'Target utilisation') AS REAL) AS target
), summary AS (
    SELECT h.hub_id, h.hub_name, w.week,
           COUNT(DISTINCT d.agent_id) AS eligible_agents, COUNT(d.agent_id) AS available_agent_days,
           COALESCE(SUM(d.attempts), 0) AS attempts
    FROM hubs h CROSS JOIN weeks w LEFT JOIN daily d ON d.hub_id = h.hub_id AND d.week = w.week
    GROUP BY h.hub_id, h.hub_name, w.week
), metrics AS (
    SELECT s.*, available_agent_days * p.standard AS standard_capacity,
           attempts / NULLIF(available_agent_days * p.standard, 0) AS utilisation,
           p.target AS target_utilisation
    FROM summary s CROSS JOIN parameters p
)
SELECT *, CASE WHEN utilisation IS NULL THEN NULL ELSE utilisation > target_utilisation END AS target_breach,
       CASE WHEN week = 2 THEN utilisation > target_utilisation ELSE 0 END AS week2_target_breach
FROM metrics ORDER BY hub_id, week;
