> Final review update: see TECHNICAL_HANDOFF.md and DEPLOYMENT_GUIDE.md. All 86 tests pass; the assessment PDF and eight-slide deck are complete locally. Public deployment remains an owner action.

# CarryBee Phase 2 handoff

## Recommendation and budget

Decline the blanket eight-hire request. Implement this 28-paid-day plan:

| Hub | Staffing action | Final roster | Programme |
| --- | --- | ---: | --- |
| Greenfield | Receive two experienced fixed-salary agents from Lakeview | 12 | None |
| Lakeview | Transfer two fixed-salary agents to Greenfield | 9 | None |
| Riverside | Retain current workforce | 12 | Agent-side hold reduction |
| Hillcrest | Hire two fixed-salary agents | 11 | None |
| Brookside | Retain current workforce | 11 | None |
| Westwood | Retain current workforce | 9 | None |

| Item | BDT |
| --- | ---: |
| Two transfers | 4,000 |
| Recruitment for two hires | 10,000 |
| Two hires x 28 days x BDT 650 | 36,400 |
| Riverside hold programme | 15,000 |
| **Total reserved** | **65,400** |
| **Remaining contingency** | **4,600** |

No projected savings are used to enlarge the BDT 70,000 spending authority.
New-agent salaries are paid in full while productivity is 60% in days 1-7.

## Q8: hiring decision

Eight fixed hires cost BDT 185,600 with 28 paid days, well above budget. Six
selective hires covering all peak baseline gaps cost BDT 139,200. Lakeview is an
eligible same-cluster donor at 56.17% Week 2 utilisation. Two transfers relieve
Greenfield while leaving nine Lakeview agents against a peak requirement of
eight. Brookside is also eligible, but Westwood needs no additional baseline
staff; a transfer there adds cost without improving the selected objective.
Riverside and Hillcrest cannot donate under the strict <75% rule.

The model evaluated 2,864 feasible fixed-pay plans, including every hub hiring
allocation affordable under the budget, every programme subset and safe transfer
quantities. The recommendation minimises total daily hub-level queue exposure
under the 85% planning target. It is optimal in that declared search space,
not a proof of global profit maximisation. The comparison also includes
variable contracts with a conservative delivery-allowance reserve.

## Q9: four-week performance and financial case

| Forecast week | Baseline attempts | Attempts after programme | Baseline 85% capacity | Plan 85% capacity | Highest hub utilisation: baseline / plan |
| --- | ---: | ---: | ---: | ---: | --- |
| 27 Oct-2 Nov | 13,898.44 | 13,898.44 | 14,756 | 15,041.60 | 96.94% / 89.97% |
| 3-9 Nov | 14,314.17 | 14,314.17 | 14,756 | 15,232.00 | 99.90% / 92.46% |
| 10-16 Nov | 14,445.07 | 14,197.72 | 14,756 | 15,232.00 | 100.88% / 85.72% |
| 17-23 Nov | 14,050.23 | 13,766.62 | 14,756 | 15,232.00 | 97.93% / 82.78% |

Network capacity cannot be pooled across hubs. With a strict 85% scheduling cap,
the end-of-week queue would change as follows:

| Week | Baseline target-cap queue | Recommended target-cap queue |
| --- | ---: | ---: |
| 1 | 736.29 | 182.51 |
| 2 | 1,711.04 | 417.86 |
| 3 | 2,758.31 | 442.14 |
| 4 | 3,588.02 | 367.46 |

These are projected planning queues, not observed overdue deliveries. At the
40-attempt standard workload, the recommended plan has no modelled queue in any
week; the baseline has temporary Hillcrest pressure but also clears by month-end.
Total planning-queue exposure falls from 50,791.64 to 8,843.54 attempt-days, an
82.59% reduction. The early weeks still require controlled operation above the
85% target, with daily workload and actual backlog checks.

The conservative programme base case gives no benefit in the first 14 days,
then removes 50% of agent-side holds. It prevents 571.36 Hold events, saving
**BDT 17,140.65** directly, and avoids **530.96 retries within the forecast**.
Another 40.40 retries would be avoided on day 29 and are not counted in capacity.
There is no separate cash saving for freed attempts: existing staff remain paid.

Incremental operating cost is **BDT 19,259.35** (new payroll minus hold charges
saved). Including all one-time costs, incremental net cash cost is
**BDT 48,259.35**. Package direct-cash ROI is **-73.79%** in the first 28 days.
No incremental delivery-fee or COD revenue is claimed. Faster delivery does not
establish another paid order. The service case, not a positive monthly cash ROI,
supports the staffing investment.

The Riverside programme by itself has 14.27% first-period direct ROI. Its
extrapolated hold-charge-only payback is 26.3 days after launch, assuming the
final two weeks' saving rate persists. This is not whole-package payback.

Sensitivities:

- Paying 26 days reduces this same plan to BDT 62,800. Re-optimising at 26 days
  selects three hires (one Riverside, two Hillcrest) plus two Lakeview transfers
  for BDT 69,700, but that alternative costs BDT 73,600 when 28 days are paid.
  Do not silently fund 28 operating days with a 26-day payroll reserve.
- A gradual 14-day programme ramp increases projected hold savings to
  BDT 25,076.09. Half effectiveness yields BDT 8,570.33; a 21-day delay yields
  BDT 8,483.56. The base does not assume either early benefit or immediate 50%.
- At +20% demand, the recommended plan ends with 709.75 attempts queued even
  at standard workload. At +10%, the standard-workload queue clears, while
  target-cap pressure rises sharply. These are uniform-daily-demand scenarios,
  not confidence intervals or route-level predictions.

## Q10: first-14-day controls

Operations should review required attempts, attendance, actual overdue orders
and hub utilisation daily. Escalate demand more than 10% above forecast for
three days, utilisation above 95% for two days, or any day above 100% standard
capacity. HR and Training review new agents on days 3/7/10/14; below 40% first-week
productivity for two days triggers coaching and route support. The Riverside
manager monitors dispatch-checklist adherence and training before day 14,
then checks for at least 25% reduction in agent-side hold rate by days 15-17.
Finance checks committed costs twice weekly and before every purchase; the
BDT 70,000 ceiling is absolute. Customer Support monitors customer holds and
returns separately. Cluster managers verify donor capacity, transfer attendance
and recipient route familiarity. Exact KPIs, thresholds, owners and mitigations
are in `outputs/strategic/risk_register.csv`.

## Verification and run

The original 49 tests remain intact. The full suite passes **79 tests, zero
failures and zero skips**. All seven original SQL files, the schema, and nine
Phase 1 CSV exports retain their original SHA-256 hashes. Scenario inputs are
independently validated against the original reference calculations.

Browser checks verify all three sections, historical filtering, a Riverside
hub selection, an over-budget scenario warning and mobile rendering with no
JavaScript errors. Real screenshots are saved under `outputs/dashboard/screenshots/`.
A fresh dependency installation passed `pip check`; the isolated dashboard
runs with no raw data, SQLite database or local analysis outputs.

```powershell
Set-Location 'C:\Users\User\OneDrive\Desktop\CarryBee-Analytics'
.\.venv\Scripts\python.exe -m streamlit run app.py
```

See `DEPLOYMENT.md` for exact private-GitHub and public Streamlit Cloud steps.
The final delivery records the actual remote/deployment status and commit
hashes; no planned URL is represented as a live app. Slides and final PDF have
not been started.

