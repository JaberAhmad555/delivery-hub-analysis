# CarryBee final review handoff

## Decision and interpretation

Transfer two experienced fixed-salary agents from Lakeview to Greenfield; hire
two fixed-salary agents at Hillcrest; implement the Riverside hold programme.
Post-action rosters: Greenfield 12, Lakeview 9, Riverside 12, Hillcrest 11,
Brookside 11, Westwood 9. Reserve BDT 65,400 and retain BDT 4,600.

The 28-day base case saves BDT 17,140.65 in projected hold charges, prevents
571.36 hold events and avoids 530.96 retries within the horizon. Another 40.40
retries fall outside it. Net incremental cash cost is BDT 48,259.35 and package
cash ROI is -73.79%. The recommendation optimises service pressure, not profit.
Programme-only ROI/payback must never be represented as whole-package returns.

## Completed and pending

Tasks 1-4 have local review artifacts. The public dashboard is **not deployed**.
The assessment remains DRAFT - NOT FOR SUBMISSION until anonymous public access
has been verified. No remote was created and nothing was uploaded or submitted.
GitHub Desktop publication and Streamlit account steps are owner actions.

Original Phase 1 SQL, Python analysis code, tests and assumptions were preserved.
`ASSUMPTIONS.md` and `REVIEW_HANDOFF.md` describe their original Phase 1 milestone;
their old scope statements are superseded by this handoff and Phase 2 outputs.

## Inputs and audit chain

- Phase 1: eight source tables -> standalone SQL -> nine result CSVs. Q1 has two
  result sets plus the required first-20 excerpt. `scenario_manifest.json`
  preserves hashes of the eight SQL/schema files and nine CSVs.
- Strategy: `src/scenario_analysis.py` -> `outputs/strategic/`. The original
  scenario search and CSVs are reused. `q8_hub_decisions.csv` is an added derived
  decision table; no baseline query was replaced.
- Dashboard: `src/prepare_dashboard_data.py` -> `dashboard_data/`. The app reads
  only this checked snapshot, with pseudonymous agents and no raw orders.
- Report/deck: `scripts/build_assessment.py` -> `verified_facts.json` plus draft
  report. The deck uses that same facts file. CSVs remain the numerical authority.
- Verification: `outputs/verification/`, `outputs/final-pytest-results.xml`,
  `outputs/dashboard/screenshots/` and `outputs/dashboard/clean-environment/`.

## Run and verify

```powershell
Set-Location 'C:\Users\User\OneDrive\Desktop\CarryBee-Analytics'
.\.venv\Scripts\python.exe -m pip install -r requirements-artifacts.txt
.\.venv\Scripts\python.exe -m pytest -q --junitxml=outputs/final-pytest-results.xml
.\.venv\Scripts\python.exe -m scripts.verify_results
.\.venv\Scripts\python.exe -m streamlit run app.py
# In a second terminal, using the actual local port:
.\.venv\Scripts\python.exe -m scripts.verify_dashboard --url http://localhost:8501/ --output outputs/dashboard/screenshots
.\.venv\Scripts\python.exe -m scripts.verify_interactions --url http://localhost:8501/ --output outputs/dashboard/screenshots
.\.venv\Scripts\python.exe -m scripts.build_assessment
.\.venv\Scripts\python.exe -m scripts.verify_artifacts
.\.venv\Scripts\python.exe -m scripts.package_final
```

Original-data integration tests need the excluded local employer CSVs and SQLite
database. A reviewer receiving only the archive can run the dashboard immediately;
an archive-only test run that skips source integration tests is not a replacement
for the full local validation recorded here.

## Rebuild the editable slides

`scripts/build_presentation.mjs PROJECT BUILD SKILL PYTHON` uses the bundled
`@oai/artifact-tool` (2.8.118) and the presentation skill's checked finalizer.
Use the bundled Node runtime, a new private BUILD directory, and set
`RUNTIME_NODE_MODULES` to its bundled node_modules. Resolve the package by a local
node_modules junction beside the script. SKILL points to the installed
presentations skill; PYTHON points to the bundled Python executable. No bundled
dependency or skill files need modification. The finalizer verifies eight
slides, native tables/charts, the budget total and embedded chart workbooks.
The original literal chart ratios are rounded to six decimal places for Excel
interoperability; all financial calculations retain their source precision.

Copy the validated BUILD/final/CarryBee_Management_Presentation.pptx to
`outputs/final/`. Copy BUILD/renders and the validation/contract JSON to their
review locations. Generate its PDF companion using:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_slide_pdf outputs/final/slide_renders outputs/final/CarryBee_Management_Presentation.pdf
```

The PDF is a faithful image rendering of the eight slides. The PPTX contains
editable text, tables, charts and four embedded workbooks. The assessment PDF
has selectable text throughout, including all SQL queries. Native PowerPoint UI
opening was not tested; package/import checks and visual renders were checked.

## Finalize only after public deployment

Follow `DEPLOYMENT_GUIDE.md`, then run the browser script against the actual
HTTPS public URL. Each browser page uses a new anonymous context.

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_dashboard --url https://YOUR-VERIFIED-APP.streamlit.app/ --output outputs/dashboard/public-verification
.\.venv\Scripts\python.exe -m scripts.build_assessment --public-url https://YOUR-VERIFIED-APP.streamlit.app/ --verification outputs/dashboard/public-verification/browser-verification.json
```

The placeholder above is a command template, not a deployed URL. Final mode
rejects missing, local or mismatched public-browser evidence and creates a
separate `CarryBee_Assessment_FINAL.pdf`, preserving the draft. Recheck the
final PDF after generation. Do not submit the draft or claim public deployment
until this last requirement is met.

## Sharing boundaries

The public source-download ZIP includes only the app and aggregate snapshot.
The private final review ZIP contains required derived agent-level SQL results,
report/deck, source, tests and documentation. It is intended for the assessment
reviewer. It excludes original data files, SQLite, virtual environments, secrets,
Git history and other archives. Do not publish the review ZIP with the app.
