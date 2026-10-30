import json
import sqlite3
from pathlib import Path
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from scripts.build_assessment import facts, final_allowed, wrap_sql
from src.config import ROOT, DB

def test_default_report_is_draft():
    assert not final_allowed(None,None)

def test_public_url_requires_successful_browser_evidence(tmp_path):
    with pytest.raises(ValueError): final_allowed('https://example.com',None)
    with pytest.raises(ValueError): final_allowed('http://localhost:8501',None)

def test_mismatched_url_cannot_finalize(tmp_path):
    file=tmp_path/'evidence.json'
    file.write_text(json.dumps({'url':'https://different.example','javascript_errors':[], 'checks':[{'http_status':200}]*3}))
    with pytest.raises(ValueError): final_allowed('https://app.example',file)

def test_matching_browser_evidence_allows_final_mode(tmp_path):
    file=tmp_path/'evidence.json'
    file.write_text(json.dumps({'url':'https://app.example/','javascript_errors':[], 'checks':[{'http_status':200}]*3}))
    assert final_allowed('https://app.example',file)

def test_wrapped_sql_preserves_all_eight_results():
    import re
    with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True) as con:
        for path in sorted((ROOT/'sql').glob('q[1-7]_*.sql')):
            for sql in re.split(r'^-- result: \w+\s*$',path.read_text(),flags=re.MULTILINE)[1:]:
                assert_frame_equal(pd.read_sql_query(sql,con),pd.read_sql_query(wrap_sql(sql),con))

def test_report_facts_reconcile_budget_and_weekly_savings():
    f=facts(); r=f['recommended']
    assert sum(a['amount_bdt'] for a in f['budget'])==70000
    assert r['budget_reserved_bdt']==65400 and r['remaining_budget_bdt']==4600
    assert sum(a['savings_bdt'] for a in f['weekly'])==pytest.approx(r['direct_hold_cost_savings_bdt'])
    assert sum(a['eight_hire_allocation'] for a in f['hubs'])==8
    assert sum(a['eight_hire_cost_bdt'] for a in f['hubs'])==185600
    assert [a['roster'] for a in f['hubs']]==[12,9,12,11,11,9]

def test_no_first_fourteen_day_programme_savings():
    f=facts()
    assert [a['savings_bdt'] for a in f['weekly'][:2]]==[0,0]
    assert f['weekly'][0]['target_capacity']==pytest.approx(15041.6)
    assert f['weekly'][1]['target_capacity']==pytest.approx(15232)
