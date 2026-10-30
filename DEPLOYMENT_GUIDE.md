# Manual deployment and local run

The dashboard is locally verified. **No public deployment URL exists yet.**
GitHub publishing and external account authentication are left to the owner.

## Run locally

```powershell
Set-Location 'C:\Users\User\OneDrive\Desktop\CarryBee-Analytics'
.\.venv\Scripts\python.exe -m streamlit run app.py
```

For a clean checkout, use Python 3.13, create a virtual environment with
`python -m venv .venv`, then run
`.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
The app uses only the checksum-verified `dashboard_data/` snapshot.

## Publish yourself

1. In GitHub Desktop, add this existing repository and publish it as **private**.
   Keep `.gitignore` in place. Do not add raw data, databases, `.venv`, secrets or review ZIPs.
2. At https://share.streamlit.io, connect your GitHub account and authorize this
   private repository. Create an app with branch `main`, entry point `app.py`,
   and Python 3.13. No secrets are needed.
3. Set viewer access to public. Open the assigned app URL in a signed-out browser.
4. Check all three sidebar pages, cluster and period filters, Riverside, and the
   eight-hire warning. Download the source ZIP and confirm it contains only app
   code and the aggregate snapshot.
5. Supply the verified URL. Run `python -m scripts.verify_dashboard --url URL
   --output outputs/dashboard/public-verification` to produce anonymous-browser
   evidence, then regenerate the final report with the command in `TECHNICAL_HANDOFF.md`.

Until this succeeds, the assessment PDF must retain **DRAFT - NOT FOR SUBMISSION**.

The deployed snapshot includes operational aggregates and pseudonymous agent
summaries. It excludes names, raw IDs, orders, logs, COD data, source-download
URLs and credentials. Private assessment reports contain the SQL-required
agent results and must be shared only with the assessment reviewer.

Official instructions: https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy
and https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
