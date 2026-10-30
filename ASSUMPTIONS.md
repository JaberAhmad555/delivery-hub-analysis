# Assumptions and limitations

## Scope and source authority

This repository implements Phase 1, Task 1 (Q1-Q7), using the supplied three-page
Data Analyst Technical Assessment and the eight supplied CSVs. The assessment's
final PDF, strategy, public dashboard and slides belong to later phases.
`app.py` is a reserved entry point, not a dashboard. No assessment result uses
synthetic data. Small synthetic fixtures exist only under `tests/` to exercise
edge cases.

## Dates, staffing and event attribution

- Historical dates are inclusive: 13-26 October 2026. Week 1 ends 19 October;
  Week 2 starts 20 October. Timestamp filters use half-open intervals ending
  27 October 00:00:00. Source timestamps have no timezone; their calendar dates
  are used as supplied, without timezone conversion.
- Joining day is eligible. Inactive agents remain eligible through 19 October,
  then leave. All active agents are available seven days a week. No leave or
  attendance roster is supplied. Headcount is taken from `agents`, never from
  agents who happen to have log events.
- One Assigned event is one attempt. Outcomes are uniquely paired using
  `(order_id, attempt_no)`. Source validation requires matching agents, same-day
  outcomes, nondecreasing assignment/outcome timestamps, valid agent eligibility
  and matching order/agent hubs. The observed source has no attribution or
  same-day chronology mismatches.
- Attempts are counted by Assigned event date, outcomes by their own event date.
  These dates match for all supplied attempts. A future cross-day outcome fails
  validation so attribution is reconsidered instead of silently mixing periods.
- A hold is an outcome of an attempt, not a terminal order status in general.
  Retry sequences must start at attempt 1, increase by one, follow a Hold on the
  next calendar day, and never retain Hold at attempt 3. Unresolved final Holds
  are permitted only at the 26 October observation boundary.
- Source `orders.final_status` is treated as the snapshot at 26 October. It is
  checked against each order's latest logged outcome. COD and delivery charges
  are imported but do not enter operational cost per delivered order.

## Metric definitions

| Query | Numerator or measure | Denominator and interpretation |
| --- | --- | --- |
| Q1 daily | Event counts by eligible agent and day | Include eligible zero-activity days. Hub mean is total deliveries / available agent-days across the whole 14-day period. |
| Q2 | Assigned events in the hub/week | Available agent-days x 40. The breach flag is strictly greater than 85%, not greater than or equal. Distinct eligible agents are also reported; agent-days remain the capacity denominator. |
| Q3 | Week 2 Hold events, including repeat holds | Agent-side share divides qualifying events by all hub Hold events. Agent-side reasons are exactly Late Dispatch, Not Attempted and Agent Time Shortage. Top two use count descending, then reason text ascending for ties. |
| Q4 | Distinct ever-held orders with each final status | All distinct orders with at least one historical Hold. Multiple hold events do not add orders. The three final-status shares sum to one where the cohort is nonempty. |
| Q5 | Returned outcome events attributed to the Assigned agent | All historical Assigned attempts attributed to that agent. Filter elapsed calendar tenure >30 days as of 26 October and ratio >15%. Include inactive agents if they qualify; do not allocate an order's final return to its earlier attempts. |
| Q6 | Staffing pay + Hold event costs + Returned event costs | Delivered outcome events in the same hub/week. There is one terminal Delivered event per delivered order, validated in ingestion. No revenue offsets or one-time interventions. |
| Q7 | Expected orders x historical attempts per new order | Divide by 7 x 40 x 85% = 238 attempts per fully productive agent/week, then round up once to a whole person. |

Zero-denominator rates are SQL NULL, blank in CSV, and `n/a` in the Markdown
tables. A zero count remains zero. Ratios in the CSVs are fractions, not
percentage points. Calculation precision is preserved; the report displays up
to six decimals. Money is BDT.

## Historical pay: explicit paid-day assumption

The PDF charges staff for each day they work but supplies no attendance file.
Following the Phase 1 request to include paid staff without assignments, every
eligible calendar day is assumed a paid working day, including zero-activity
days. Inactive staff receive pay through Week 1 only. This is an operational
cost estimate under a stated assumption, not a payroll attendance reconciliation.

- Fixed: BDT 16,900 / 26 = BDT 650 per eligible day.
- Variable: BDT 300 per eligible day plus BDT 14 per Delivered outcome.
- Holds: BDT 30 for each Hold event, including repeat holds.
- Returns: BDT 55 for each Returned outcome.
- `staffing_pay_bdt` = fixed salary + daily allowances + delivery allowances.
- `operating_cost_bdt` adds hold and return costs to staffing pay.
- The 26-day divisor converts monthly fixed salary into a daily rate. It does
  not reduce seven-day weekly availability or weekly paid days. A 28-calendar-day
  historical-rate projection would not equal one monthly salary; Phase 2 must
  distinguish that projection from the specified new-hire monthly budget.

There are 882 eligible historical agent-days, including 28 with zero Assigned
events. Excluding those days would understate staffing cost and inflate
productivity and utilisation.

## Forecast: period-flow multiplier and its limits

The baseline multiplier is calculated separately for each hub:

`Week 2 Assigned events / orders created in Week 2`

This estimates actual attempt workload per new arrival in the most recent week,
including retries of orders carried in from Week 1. It avoids treating a
distinct order as a single attempt, and it uses the observed Week 2 workload
under the higher demand regime. It is a period-flow estimate, not a completed
order-cohort lifetime estimate. The four forecast weeks are 27 October-2 November,
3-9 November, 10-16 November and 17-23 November.

Assumptions and limitations:

- The Week 2 retry, backlog and return mix persists. The short 14-day observation
  window does not support a seasonal model or confidence interval.
- Some repeat attempts on orders arriving near 26 October occur beyond the
  observation window. Week 2 also contains carry-in retries. These flows need
  not offset exactly. No unobserved attempts are invented.
- A multiplier based only on attempts already observed for Week 2-created
  orders would be right-censored; using only completed orders would select a
  faster-resolution cohort. Neither is substituted silently.
- Expected attempts may be fractional because they are an expectation. The
  staffing ceiling is applied after the full calculation; no rounded displayed
  multiplier or intermediate rounded attempt count drives staffing.
- The workforce is the 62 agents Active and joined by 26 October, held constant
  across the forecast. Availability is all seven calendar days of each week.
- `staffing_gap = required_agents - current_active_agents`. Positive values
  indicate a capacity shortage; negative values indicate surplus. `shortage`
  and `surplus` separately expose positive magnitudes.
- Gaps are fully productive agent equivalents rounded to whole people. They
  are not an approved hiring plan. New staff at 60% first-week productivity
  would require a separate ramp-up calculation before turning gaps into hires.
- Q7 includes no hiring, transfers or hold-programme benefits. The preserved
  source rules must constrain those scenarios in Phase 2.

## Rules retained for Phase 2

Hiring is BDT 5,000 once per new agent, excluding salary. Transfers cost BDT
2,000 per agent and are permitted only within a cluster, from hubs with
pre-transfer Week 2 utilisation strictly below 75%. The hold programme costs
BDT 15,000 per hub and removes 50% of agent-side holds at full effectiveness
after 14 days. The source gives the full-effect date but no intermediate ramp
curve. New agents produce at 60% for their first seven days. The next-month
budget is BDT 70,000 including all one-time interventions and new-agent salary.

These rules are retained, not applied as benefits or expenses in observed
historical Q1-Q6 metrics. There is no Phase 1 intervention recommendation.

## Reproducibility and validation limits

All eight CSVs are imported as distinct source tables. Keys, date formats,
status values, join cardinalities, eligibility, attempt/outcome pairs, final
statuses, policy values and forecast coverage are validated before replacement
of the SQLite database. A failed rebuild preserves the preceding database.

Every SQL result is compared against pandas/Python calculations from the
original CSVs. The financial reference uses Decimal arithmetic; the forecast
reference uses exact fractions and an independent ceiling. Expected assessment
counts and supplied utilisation/hold references are assertions only, never
query output constants. The source/SQL hashes and runtime versions are saved
with each successful run. Validation establishes consistency with the supplied
snapshot, not accuracy of the employer's underlying collection process.

No unresolved data discrepancies were found. Independent review should confirm
the paid-day assumption and the forecasting multiplier before Phase 2.
