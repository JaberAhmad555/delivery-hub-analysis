"""Refresh narrative only from existing validated scenario results; no new search."""
import json
import pandas as pd
from src.scenario_analysis import STRATEGIC,Plan,load_model,write_report

if __name__=='__main__':
    info=json.loads((STRATEGIC/'scenario_manifest.json').read_text())
    r=info['recommended']
    plan=Plan(r['name'],tuple(r['hires']),tuple(tuple(t) for t in r['transfers']),tuple(r['programmes']))
    tables={name:pd.read_csv(STRATEGIC/f'{name}.csv') for name in ['scenario_comparison','weekly_staffing_plan','budget_allocation','risk_register','sensitivity_analysis']}
    write_report(load_model(),plan,tables['scenario_comparison'],tables['weekly_staffing_plan'],tables,info)
    print('Strategic narrative refreshed from existing validated results; scenario CSVs unchanged.')
