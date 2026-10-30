"""Browser smoke checks and genuine screenshots of all Streamlit sections.

Run a Streamlit server first. This script never deploys or uploads anything.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


def capture(page, destination):
    page.locator('[data-testid="stPlotlyChart"] .js-plotly-plot').first.wait_for()
    # Streamlit scrolls its main element rather than the document. Use a real
    # taller viewport to include the entire page, without altering page content.
    height = page.locator('[data-testid="stMain"]').evaluate("el => el.scrollHeight")
    page.set_viewport_size({"width": 1600, "height": min(max(int(height) + 100, 1150), 5500)})
    page.screenshot(path=str(destination), full_page=True, animations="disabled")


def verify(url, output):
    output.mkdir(parents=True, exist_ok=True)
    checks = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        errors = []
        for view, title, filename in [
            ("overview", "Operations overview", "01-executive-overview.png"),
            ("hubs", "Hub diagnostics", "02-hub-diagnostics.png"),
            ("forecast", "Plan the next four weeks", "03-forecast-and-budget.png"),
        ]:
            page = browser.new_page(viewport={"width": 1600, "height": 1150}, device_scale_factor=1)
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(url + "?view=" + view, wait_until="networkidle")
            assert response.status == 200
            expect(page.get_by_role("heading", name=title, exact=True)).to_be_visible()
            expect(page.locator('[data-testid="stException"]')).to_have_count(0)
            expect(page.locator('[data-testid="stCode"]')).to_have_count(0)
            if view == "hubs":
                page.get_by_role("combobox", name="Select hub").click()
                page.get_by_role("option", name="Riverside", exact=True).click()
                expect(page.locator('[data-testid="stMetricValue"]').first).to_have_text("5,332")
            capture(page, output / filename)
            checks.append({"page": title, "http_status": response.status, "charts": page.locator('[data-testid="stPlotlyChart"]').count(),
                           "screenshot": filename, "viewport": page.viewport_size})
            if view == "overview":
                page.get_by_role("combobox", name="Historical period").click()
                page.get_by_role("option", name="Week 2 · 20–26 Oct", exact=True).click()
                expect(page.locator('[data-testid="stMetricValue"]').first).to_have_text("12,255")
                checks.append({"check": "Historical period filter updates metrics", "status": "passed"})
            if view == "forecast":
                page.get_by_text("Payroll, ramp and downside sensitivities", exact=True).click()
                page.get_by_text("First-14-day risk controls", exact=True).click()
                capture(page, output / "04-forecast-sensitivities-and-risks.png")
                page.get_by_role("combobox", name="Scenario", exact=True).click()
                page.get_by_role("option", name="Eight fixed hires", exact=True).click()
                expect(page.locator('[data-testid="stMetricValue"]').first).to_have_text("BDT 185,600")
                expect(page.get_by_text("This scenario exceeds BDT 70,000", exact=False)).to_be_visible()
                checks.append({"check": "Scenario switch updates cost and over-budget warning", "status": "passed"})
            page.close()
        mobile = browser.new_page(viewport={"width": 430, "height": 932}, device_scale_factor=1)
        mobile.goto(url + "?view=overview", wait_until="networkidle")
        expect(mobile.get_by_role("heading", name="Operations overview", exact=True)).to_be_visible()
        expect(mobile.locator('[data-testid="stException"]')).to_have_count(0)
        mobile.screenshot(path=str(output / "05-mobile-overview.png"), full_page=True)
        checks.append({"check": "430px responsive overview renders", "status": "passed"})
        browser.close()
    if errors:
        raise RuntimeError("Browser JavaScript errors: " + str(errors))
    result = {"captured_at_utc": datetime.now(timezone.utc).isoformat(), "url": url, "browser": "Playwright Chromium, real rendered app",
              "javascript_errors": errors, "checks": checks}
    (output / "browser-verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8501/")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "outputs" / "dashboard" / "screenshots")
    args = parser.parse_args()
    verify(args.url, args.output)
