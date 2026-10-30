"""Run standalone SQL, independently validate every result, then export."""
import argparse
import json
import re
import sqlite3
from pathlib import Path

import pandas as pd

from src.config import DB, OUTPUTS, RAW, ROOT
from src.load_data import build_database, read_sources
from src.validation import validate_results, validate_sources


def run_queries(connection: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    results = {}
    for path in sorted((ROOT / "sql").glob("q[1-7]_*.sql")):
        sections = re.split(r"^-- result: (\w+)\s*$", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
        for name, query in zip(sections[1::2], sections[2::2]):
            results[name] = pd.read_sql_query(query, connection)
    return results


def run_analysis(raw_dir: Path = RAW, db_path: Path = DB, output_dir: Path = OUTPUTS, rebuild: bool = True) -> dict:
    from src.export_results import export_results

    frames = read_sources(raw_dir)
    source_audit = build_database(raw_dir, db_path) if rebuild else validate_sources(frames)
    # Reuse is read-only; comparisons also catch a stale database versus changed CSVs.
    connection = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        results = run_queries(connection)
    finally:
        connection.close()
    audit = {**source_audit, **validate_results(frames, results)}
    audit["zero_activity_agent_days"] = int(results["q1_agent_day"].attempts.eq(0).sum())
    export_results(results, audit, raw_dir, output_dir)
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--output-dir", type=Path, default=OUTPUTS)
    parser.add_argument("--reuse-db", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_analysis(args.raw_dir, args.db, args.output_dir, not args.reuse_db), indent=2))
