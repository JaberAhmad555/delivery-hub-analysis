"""Validate original CSVs and atomically create the eight-table SQLite database."""
import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

from src.config import DB, HEADERS, RAW, ROOT
from src.download_data import validate_csv


def read_sources(raw_dir: Path = RAW) -> dict[str, pd.DataFrame]:
    frames = {}
    for table in HEADERS:
        path = raw_dir / f"{table}.csv"
        validate_csv(path.read_bytes(), table)
        frames[table] = pd.read_csv(path, keep_default_na=False, dtype=str)
    numeric = {"orders": ["cod_amount", "delivery_charge"], "order_logs": ["attempt_no"],
               "agent_salary": ["monthly_salary", "daily_allowance", "allowance_per_delivery"],
               "costs": ["amount_bdt"], "volume_forecast": ["expected_orders"]}
    for table, columns in numeric.items():
        for column in columns:
            frames[table][column] = pd.to_numeric(frames[table][column], errors="raise")
    return frames


def build_database(raw_dir: Path = RAW, db_path: Path = DB) -> dict:
    from src.validation import validate_sources

    frames = read_sources(raw_dir)
    audit = validate_sources(frames)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    temp = db_path.with_suffix(db_path.suffix + ".tmp")
    if temp.exists():
        temp.unlink()
    try:
        with sqlite3.connect(temp) as connection:
            connection.executescript((ROOT / "sql" / "00_schema.sql").read_text(encoding="utf-8"))
            for table in ["hubs", "agent_salary", "agents", "orders", "order_logs", "costs", "rules", "volume_forecast"]:
                frame = frames[table].copy()
                if table == "order_logs":
                    frame["hold_reason"] = frame.hold_reason.replace("", None)
                frame.to_sql(table, connection, if_exists="append", index=False)
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise ValueError("Foreign key validation failed")
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite integrity check failed")
        # sqlite3 context manager commits but does not close the connection.
        connection.close()
        temp.replace(db_path)
    except Exception:
        if "connection" in locals():
            connection.close()
        temp.unlink(missing_ok=True)
        raise
    return audit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    parser.add_argument("--db", type=Path, default=DB)
    args = parser.parse_args()
    print(json.dumps(build_database(args.raw_dir, args.db), indent=2))
