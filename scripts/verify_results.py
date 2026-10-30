"""Read-only independent verification; never rewrites Phase 1 results."""
import hashlib
import json
import sqlite3
from pathlib import Path
import pandas as pd
from pandas.testing import assert_frame_equal
from src.config import ROOT, DB
from src.analysis import run_queries
from src.load_data import read_sources
from src.validation import validate_sources, validate_results
from src.dashboard_data import load_snapshot

def verify():
    frames = read_sources()
    audit = validate_sources(frames)
    with sqlite3.connect(DB.resolve().as_uri() + '?mode=ro', uri=True) as con:
        results = run_queries(con)
    audit.update(validate_results(frames, results))
    for name, frame in results.items():
        assert_frame_equal(frame, pd.read_csv(ROOT / 'outputs' / (name+'.csv')), check_dtype=False)
    assert_frame_equal(results['q1_agent_day'].head(20), pd.read_csv(ROOT/'outputs/q1_first20.csv'), check_dtype=False)
    manifest=json.loads((ROOT/'outputs/strategic/scenario_manifest.json').read_text())
    for name, digest in manifest['phase1_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, name
    tables, metadata=load_snapshot()
    for name in ['scenario_comparison','weekly_staffing_plan','budget_allocation','sensitivity_analysis']:
        assert_frame_equal(tables[name],pd.read_csv(ROOT/'outputs/strategic'/f'{name}.csv'),check_dtype=False)
    scenarios=tables['scenario_comparison']; rec=scenarios[scenarios.scenario.str.startswith('Recommended')].iloc[0]
    assert rec.budget_reserved_bdt == 65400
    assert rec.remaining_budget_bdt == 4600
    assert abs(rec.avoided_hold_events*30-rec.direct_hold_cost_savings_bdt)<1e-7
    assert abs(rec.budget_reserved_bdt-rec.direct_hold_cost_savings_bdt-rec.total_incremental_cash_cost_bdt)<1e-7
    assert abs(rec.avoided_reattempts_in_horizon+rec.avoided_retries_after_horizon-rec.avoided_hold_events)<1e-7
    audit.update({'source_counts':{k:len(v) for k,v in frames.items()},'phase1_hashes_unchanged':len(manifest['phase1_sha256']),
                  'sql_result_sets_compared':len(results),'snapshot_hashes_verified':len(metadata['files']),
                  'budget_arithmetic':'passed','hold_benefit_accounting':'passed'})
    destination=ROOT/'outputs/verification'; destination.mkdir(parents=True,exist_ok=True)
    (destination/'independent_results.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(audit,indent=2))
    return audit

if __name__=='__main__': verify()
