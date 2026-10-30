-- Q5: returned outcomes attributed to the corresponding Assigned agent.
-- Pairing key (order_id, attempt_no) is unique on each side and validated by ingestion.
-- Tenure is elapsed calendar days at 2026-10-26, strictly >30; no active-only filter.
-- Outcome ratio is Returned attempts / all Assigned attempts, strictly >15%.
-- result: q5_high_return_agents
WITH paired AS (
    SELECT s.agent_id, t.status
    FROM order_logs s JOIN order_logs t
      ON s.order_id = t.order_id AND s.attempt_no = t.attempt_no AND t.status != 'Assigned'
    WHERE s.status = 'Assigned' AND s.event_time >= '2026-10-13' AND s.event_time < '2026-10-27'
), metrics AS (
    SELECT a.agent_id, a.agent_name, a.hub_id, h.hub_name, a.active_status,
           CAST(julianday('2026-10-26') - julianday(a.joining_date) AS INTEGER) AS tenure_days,
           COUNT(*) AS attempts, SUM(p.status = 'Returned') AS returned_attempts,
           1.0 * SUM(p.status = 'Returned') / COUNT(*) AS return_ratio
    FROM paired p JOIN agents a ON a.agent_id = p.agent_id JOIN hubs h ON h.hub_id = a.hub_id
    GROUP BY a.agent_id, a.agent_name, a.hub_id, h.hub_name, a.active_status, a.joining_date
)
SELECT * FROM metrics WHERE tenure_days > 30 AND return_ratio > 0.15
ORDER BY return_ratio DESC, agent_id;
