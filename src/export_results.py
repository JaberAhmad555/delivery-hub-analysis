"""Export full-precision CSVs, an audit manifest and report-ready Markdown tables."""
import hashlib
import json
import platform
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.config import FILE_IDS, OUTPUTS, RAW, ROOT


def markdown_table(frame: pd.DataFrame) -> str:
    def cell(value):
        if pd.isna(value):
            return "n/a"
        if isinstance(value, float):
            return f"{value:,.6f}".rstrip("0").rstrip(".")
        return str(value).replace("|", "\\|").replace("\n", " ")
    rows = ["| " + " | ".join(map(str, frame.columns)) + " |", "| " + " | ".join(["---"] * len(frame.columns)) + " |"]
    rows += ["| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None)]
    return "\n".join(rows)


def export_results(results: dict, audit: dict, raw_dir: Path = RAW, output_dir: Path = OUTPUTS) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    exports = {**results, "q1_first20": results["q1_agent_day"].head(20)}
    for name, frame in exports.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig", na_rep="")
    (output_dir / "validation.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
                "sqlite": sqlite3.sqlite_version, "pandas": pd.__version__, "sources": {}, "sql_sha256": {}}
    for table, file_id in FILE_IDS.items():
        manifest["sources"][table] = {"url": f"https://drive.google.com/uc?export=download&id={file_id}",
                                       "sha256": hashlib.sha256((raw_dir / f"{table}.csv").read_bytes()).hexdigest()}
    for path in sorted((ROOT / "sql").glob("*.sql")):
        manifest["sql_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    sections = ["# CarryBee Express: Phase 1 SQL results", "Historical: 13-26 October 2026. Forecast: 27 October-23 November 2026.",
                "Q1-Q6 are observed metrics. Q7 is a baseline projection. Ratios are fractions (0.85 = 85%); currency is BDT. "
                "Tables display up to six decimals; CSVs retain computation precision. Blank CSV fields mean unavailable, not zero.",
                "Definitions, limitations and salary assumptions: ../ASSUMPTIONS.md. Query sources: ../sql/. "
                "validation.json records independent comparisons; run_manifest.json records source and SQL hashes.",
                "## Source audit", "```json\n" + json.dumps(audit, indent=2) + "\n```"]
    titles = {"q1_first20": "Q1: first 20 agent-days (day, hub, agent order)", "q1_hub_summary": "Q1: full hub summary",
              "q2_utilisation": "Q2: weekly utilisation", "q3_hold_reasons": "Q3: Week 2 hold reasons",
              "q4_held_orders": "Q4: final outcomes for distinct ever-held orders", "q5_high_return_agents": "Q5: high-return agents",
              "q6_delivery_costs": "Q6: historical operating costs (BDT)", "q7_staffing_forecast": "Q7: projected staffing, without interventions"}
    for name, title in titles.items():
        sections += ["## " + title, markdown_table(exports[name]) if len(exports[name]) else "No qualifying records."]
    (output_dir / "results.md").write_text("\n\n".join(sections) + "\n", encoding="utf-8")
