-- Q6: every eligible day is assumed paid, even without an Assigned event.
-- Fixed daily pay = monthly salary / 26; variable pay = daily + delivery allowance.
-- Include every hold/return event; exclude one-time strategic interventions and COD.
-- Rates come from agent_salary, costs and rules source tables; currency is BDT.
-- result: q6_delivery_costs
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
    SELECT CAST((SELECT value FROM rules WHERE rule = 'Working days per month') AS REAL) AS paid_days,
           (SELECT amount_bdt FROM costs WHERE what = 'A hold') AS hold_rate,
           (SELECT amount_bdt FROM costs WHERE what = 'A return') AS return_rate
), pay AS (
    SELECT d.*, s.monthly_salary / p.paid_days AS fixed_salary,
           s.daily_allowance, d.delivered * s.allowance_per_delivery AS delivery_allowance,
           d.holds * p.hold_rate AS hold_cost, d.returned * p.return_rate AS return_cost
    FROM daily d JOIN agent_salary s ON s.salary_type = d.salary_type CROSS JOIN parameters p
), totals AS (
    SELECT h.hub_id, h.hub_name, w.week, COUNT(d.agent_id) AS paid_agent_days,
           COALESCE(SUM(d.delivered), 0) AS delivered_orders,
           COALESCE(SUM(d.fixed_salary), 0) AS fixed_salary_bdt,
           COALESCE(SUM(d.daily_allowance), 0) AS daily_allowances_bdt,
           COALESCE(SUM(d.delivery_allowance), 0) AS delivery_allowances_bdt,
           COALESCE(SUM(d.hold_cost), 0) AS hold_cost_bdt,
           COALESCE(SUM(d.return_cost), 0) AS return_cost_bdt
    FROM hubs h CROSS JOIN weeks w LEFT JOIN pay d ON d.hub_id = h.hub_id AND d.week = w.week
    GROUP BY h.hub_id, h.hub_name, w.week
), staffing AS (
    SELECT *, fixed_salary_bdt + daily_allowances_bdt + delivery_allowances_bdt AS staffing_pay_bdt FROM totals
), total_cost AS (
    SELECT *, staffing_pay_bdt + hold_cost_bdt + return_cost_bdt AS operating_cost_bdt FROM staffing
)
SELECT *, operating_cost_bdt / NULLIF(delivered_orders, 0) AS cost_per_delivered_order_bdt
FROM total_cost ORDER BY hub_id, week;
