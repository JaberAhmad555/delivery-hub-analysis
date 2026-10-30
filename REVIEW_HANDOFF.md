# Phase 1 independent-review handoff

Working directory: `C:\Users\User\OneDrive\Desktop\CarryBee-Analytics`.
Implementation and execution used Python 3.13.5, pandas 2.3.3, SQLite, requests
and pytest. The source is the supplied assessment and eight supplied CSV IDs.
No dashboard, strategic recommendation, slides or final PDF was built.

## Actual source and output counts

| Source | Rows |
| --- | ---: |
| hubs | 6 |
| agents | 64 (62 Active, 2 Inactive) |
| orders | 22,789 |
| order_logs | 51,190 |
| agent_salary | 2 |
| costs | 5 |
| rules | 8 |
| volume_forecast | 24 |

There are 25,595 unique Assigned attempts, each matched to exactly one outcome:
21,078 Delivered, 3,042 Hold and 1,475 Returned. There are no missing pairs,
attribution mismatches or event-date mismatches. The Q1 table has 882 eligible
agent-days, including 28 zero-activity days.

All supplied row-count, utilisation and Riverside hold checks passed. Each of
the eight SQL result sets passed the independent pandas/Python reference.
Automated execution: **49 passed, 0 failed, 0 skipped**. Original test run:
14.27 seconds. Machine-readable evidence is in `outputs/pytest-results.xml`;
console evidence is in `outputs/pytest-output.txt`.

## Important numerical findings

| Hub | Week 1 utilisation | Week 2 utilisation | Week 2 cost/delivery (BDT) | Required agents, forecast weeks 1/2/3/4 | Current agents | Staffing gap, weeks 1/2/3/4 |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| Greenfield | 62.50% | 88.64% | 26.70 | 12 / 12 / 12 / 12 | 10 | +2 / +2 / +2 / +2 |
| Lakeview | 53.47% | 56.17% | 37.01 | 7 / 8 / 8 / 8 | 11 | -4 / -3 / -3 / -3 |
| Riverside | 67.89% | 90.80% | 46.33 | 13 / 14 / 14 / 13 | 12 | +1 / +2 / +2 / +1 |
| Hillcrest | 77.10% | 95.87% | 28.07 | 11 / 11 / 11 / 11 | 9 | +2 / +2 / +2 / +2 |
| Brookside | 65.68% | 71.49% | 37.87 | 9 / 10 / 10 / 10 | 11 | -2 / -1 / -1 / -1 |
| Westwood | 66.79% | 80.36% | 28.52 | 9 / 9 / 9 / 9 | 9 | 0 / 0 / 0 / 0 |

- Week 2 utilisation exceeds 85% at Greenfield, Riverside and Hillcrest.
- Riverside has 874 Week 2 Hold events, including 563 agent-side events (64.42%).
  Its top reasons are Late Dispatch (312) and Customer Unreachable (156).
- There are 2,599 distinct ever-held orders: 2,118 finally Delivered, 245
  Returned and 236 still Hold at the observation boundary.
- Q5 identifies Brookside agents A1045 (94/349 = 26.93%), A1046
  (91/414 = 21.98%) and A1047 (72/413 = 17.43%). Each has over 30 days' tenure.
- Week 1 operating cost is BDT 360,918 for 9,670 deliveries. Week 2 operating
  cost is BDT 385,313 for 11,408 deliveries. Costs include all eligible paid days.
- Week 2 attempts/new-order multipliers are 1.072138 Greenfield, 1.071871
  Lakeview, 1.393151 Riverside, 1.079053 Hillcrest, 1.094978 Brookside and
  1.073701 Westwood. Staffing uses the unrounded ratios.

The forecast is a no-intervention baseline. Positive gaps are capacity shortages,
not approved hire counts. Transfers, a hold programme, hiring ramp-up and the
BDT 70,000 budget remain Phase 2 work.

## Commands executed

From the project directory, the execution included:

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install 'pandas>=2.2.3,<3' 'requests>=2.32,<3' 'pytest>=8,<10'
git init
git branch -m main
.\.venv\Scripts\python.exe -m src.download_data
.\.venv\Scripts\python.exe -m src.analysis
.\.venv\Scripts\python.exe -m pytest -q --junitxml=outputs\pytest-results.xml 2>&1 | Tee-Object -FilePath outputs\pytest-output.txt
git diff --cached --check
git commit -m 'Implement and verify eight-table ingestion and Q1-Q7 SQL analysis'
```

The resolved direct dependency versions were then pinned in `requirements.txt`.
Separate loader and reuse-database CLI checks and Git status checks complete the
handoff; their console evidence is saved under `outputs/`.

## Independent review priorities

1. Confirm that every eligible calendar day is a paid day in the absence of
   attendance records, including the 28 zero-activity agent-days.
2. Review the period-flow attempt multiplier, carry-in work and right-censoring
   at 26 October before adopting the baseline for strategy.
3. Trace Q5 attribution through `(order_id, attempt_no)`, and Q4 through the
   distinct ever-held order cohort. These are intentionally different grains.
4. Confirm forecast gaps are interpreted as fully productive capacity, with the
   60% new-hire ramp applied only in a later intervention scenario.

There are no unresolved source discrepancies or failed checks. GitHub CLI is
unavailable in the checked environment, so no remote was created or pushed.
README includes exact CLI installation, authentication and private repository
creation commands. Local commit hashes are supplied in the completion handoff.
