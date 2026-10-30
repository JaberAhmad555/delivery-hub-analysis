# CarryBee operations analysis - Phase 1

Reproducible Python 3.13 / SQLite implementation of Q1-Q7 from the supplied
Data Analyst Technical Assessment. It downloads eight CSVs, validates and imports
them, executes seven standalone SQL files, independently compares their results
with pandas/Python, and exports nine CSVs plus consolidated report-ready tables.

Scope: SQL and verification only. Strategy, Streamlit/Plotly dashboard,
presentation and final PDF are deferred until independent review.

## Windows setup and run

Run these commands in PowerShell. Activation is unnecessary, so PowerShell's
script-execution policy does not need to change.

```powershell
Set-Location 'C:\Users\User\OneDrive\Desktop\CarryBee-Analytics'
py -3.13 --version
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.download_data
.\.venv\Scripts\python.exe -m src.analysis
.\.venv\Scripts\python.exe -m pytest -q --junitxml=outputs\pytest-results.xml
```

The existing project environment has already been created and run. For later
reruns use the final three commands. Python 3.13.5 is the verified interpreter.
SQLite ships with Python; no server or separate SQLite installation is needed.

To save console evidence in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m src.analysis 2>&1 | Tee-Object -FilePath outputs\analysis-output.txt
if ($LASTEXITCODE -ne 0) { throw 'Analysis failed' }
.\.venv\Scripts\python.exe -m pytest -q --junitxml=outputs\pytest-results.xml 2>&1 | Tee-Object -FilePath outputs\pytest-output.txt
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
```

Useful separate commands:

```powershell
# Validate and rebuild the database without executing assessment queries:
.\.venv\Scripts\python.exe -m src.load_data
# Run queries against the existing database; still compare with original CSVs:
.\.venv\Scripts\python.exe -m src.analysis --reuse-db
# Download fresh copies; never replace an existing CSV with an HTML error page:
.\.venv\Scripts\python.exe -m src.download_data --force
# Edge-case tests without employer-supplied CSVs:
.\.venv\Scripts\python.exe -m pytest -q -m 'not integration'
```

Use `--raw-dir`, `--db`, and `--output-dir` on `src.analysis` to override paths.
Paths default relative to the repository, not the shell's current directory.
The supplied assessment is a fixed snapshot; changed source policies or
reference totals fail validation and require investigation.

## Project layout

```text
CarryBee-Analytics/
|-- app.py                         # Phase 2 placeholder
|-- data/
|   |-- raw/                       # Eight CSVs and source_manifest.json, ignored
|   `-- processed/carrybee.sqlite3  # Generated, ignored
|-- sql/
|   |-- 00_schema.sql
|   |-- q1_productivity.sql
|   |-- q2_utilisation.sql
|   |-- q3_hold_reasons.sql
|   |-- q4_held_orders.sql
|   |-- q5_high_return_agents.sql
|   |-- q6_delivery_costs.sql
|   `-- q7_staffing_forecast.sql
|-- src/
|   |-- __init__.py
|   |-- config.py
|   |-- download_data.py
|   |-- load_data.py
|   |-- analysis.py
|   |-- validation.py
|   `-- export_results.py
|-- tests/                         # SQL edge cases, download tests, source audits
|-- outputs/                       # CSVs, results.md, manifests and test evidence
|-- requirements.txt
|-- pytest.ini
|-- ASSUMPTIONS.md
|-- REVIEW_HANDOFF.md
|-- README.md
|-- .gitattributes
`-- .gitignore
```

`config.py` is the small addition to the requested structure for shared source
IDs, headers and paths. SQL files rely only on the eight source tables, with no
custom Python SQL functions or precomputed result tables. Open the generated
database in a SQLite client and run any Q file directly. Q1 has two independent
SELECT statements: the complete agent-day table, then the hub summary. The
runner recognizes `-- result:` labels to export each result separately; the
labels are ordinary SQL comments.

## Outputs and definitions

| File | Contents |
| --- | --- |
| `q1_agent_day.csv` | All 882 eligible agent-days, including 28 zero-activity days |
| `q1_first20.csv` | First 20 rows in day/hub/agent order |
| `q1_hub_summary.csv` | All six hub productivity summaries |
| `q2_utilisation.csv` | Attempts, eligible agents, agent-days, capacity, utilisation and flags |
| `q3_hold_reasons.csv` | Week 2 holds, agent-side share and deterministic top two reasons |
| `q4_held_orders.csv` | Distinct ever-held orders and final-status proportions |
| `q5_high_return_agents.csv` | Three qualifying agents with denominators and tenure |
| `q6_delivery_costs.csv` | Twelve hub/week payroll and cost decompositions, BDT |
| `q7_staffing_forecast.csv` | Twenty-four projected hub/weeks, multiplier and staffing gaps |
| `results.md` | Consolidated report-ready tables, including Q1 first 20 and full hub summary |
| `validation.json` | Source audit, independent result comparisons and reference checks |
| `run_manifest.json` | Source URLs/hashes, SQL hashes and runtime versions |
| `pytest-output.txt`, `pytest-results.xml` | Saved console and machine-readable test evidence |

Ratios are fractions (0.85 = 85%). CSV blank cells represent unavailable results.
All historical costs include paid zero-activity eligible days. Forecast attempts
use each hub's Week 2 Assigned events / Week 2 newly created orders; they are
then divided by 238 attempts per agent-week and rounded up. Current workforce
remains fixed, with seven available days each week. Details, including boundary
censoring, are in [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Source downloads and manual recovery

The downloader uses the requested Google Drive URL, bounded downloads, request
timeouts and retries for transient errors. It checks UTF-8 decoding, content
type, HTML signatures, exact headers, row widths and nonempty contents before
replacing files. The loader then checks semantic validity. No mock dataset or
HTML response can be used as assessment data.

If Google Drive requires login, denies access or returns a confirmation page,
open the corresponding link below in a browser. Download the actual CSV and
save it under `data\raw\` with the exact filename. Rerun the downloader without
`--force` to validate local files, then run the analysis. Do not use Save Page.

| File | Supplied source |
| --- | --- |
| hubs.csv | [Download](https://drive.google.com/uc?export=download&id=1nMXHUYxfNfOu7Evpcw1I05G8KtWzfozd) |
| agents.csv | [Download](https://drive.google.com/uc?export=download&id=1G3gVf87OD1UY7pMBSl9jkpXRXbnJiLaH) |
| orders.csv | [Download](https://drive.google.com/uc?export=download&id=1dXDPB_C5iYB75ghr3POorOw8jWKpHWjH) |
| order_logs.csv | [Download](https://drive.google.com/uc?export=download&id=1OjRD49U9aF_2WnN5LO-iptAFYg8sGOch) |
| agent_salary.csv | [Download](https://drive.google.com/uc?export=download&id=1mszp5gdvWmk04wh-VQri-krBOot99n1u) |
| costs.csv | [Download](https://drive.google.com/uc?export=download&id=1OLCIykkUxkzsZUOKC5Y6aFaKHv0-eqzc) |
| rules.csv | [Download](https://drive.google.com/uc?export=download&id=1fDg113qN_IlMPzNhoPY9AzF8KBz_jD1Y) |
| volume_forecast.csv | [Download](https://drive.google.com/uc?export=download&id=1Im-j7UJa5YbcqoB9_iUed-dooipSSNUp) |

## Verification

The full original-data run passes **49 tests, 0 failures, 0 skips**. Tests cover
join uniqueness and foreign keys, attempt/outcome matching and attribution,
period boundaries, joining/departure eligibility, hold classification and ties,
distinct held-order cohorts, strict tenure/return/utilisation thresholds,
zero denominators, paid zero-activity staff, financial totals, forecast
multipliers/ceilings, safe failed downloads and preservation of a previous
database after a failed rebuild. Integration tests compare all eight SQL result
sets with independent original-data calculations and all supplied references.

Without original data, integration tests explicitly skip; an edge-case-only run
does not establish assessment validation. Expected values live only in validation
assertions/tests, never SQL outputs. See [REVIEW_HANDOFF.md](REVIEW_HANDOFF.md)
for numerical findings and review priorities.

## Git and private GitHub publishing

The local repository uses branch `main`. Employer raw data, databases, generated
results, secrets, virtual environments and temporary files are ignored. Only
source, tests, documentation and directory markers are committed.

GitHub CLI was not available on PATH or in the checked standard installation
locations, so authentication could not be established and no remote repository
was created. The exact remaining commands are:

```powershell
# Install only if GitHub CLI is not already available:
winget install --id GitHub.cli --exact --source winget
# Open a new PowerShell window after installation, then:
Set-Location 'C:\Users\User\OneDrive\Desktop\CarryBee-Analytics'
gh auth login --hostname github.com --git-protocol https --web
gh auth status --hostname github.com
gh api user --jq .login
# Confirm the displayed account is JaberAhmad555 before creating the repository.
gh repo create JaberAhmad555/carrybee-operations-analysis --private --source . --remote origin --push
gh repo view JaberAhmad555/carrybee-operations-analysis --json url,visibility
```

If that repository already exists, inspect it before attaching a remote; do not
overwrite it or force-push. No fabricated commits or contribution dates are used.
