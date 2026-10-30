"""Real navigation, cluster filtering, chart legend/data and source download checks."""
import argparse
import json
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

def verify(url,output):
    output.mkdir(parents=True,exist_ok=True); evidence={'url':url,'checks':[],'chart_traces':{}}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':1600,'height':1100},accept_downloads=True)
        page.goto(url,wait_until='networkidle')
        for label,title in [('Hub Diagnostics','Hub diagnostics'),('Forecast and Budget','Plan the next four weeks'),('Executive Overview','Operations overview')]:
            page.locator('[data-testid="stSidebar"]').get_by_text(label,exact=True).click()
            expect(page.get_by_role('heading',name=title,exact=True)).to_be_visible()
        evidence['checks'].append('Sidebar navigation: all three pages')
        # Remove two selected clusters through their accessible remove buttons.
        page.get_by_role('button',name='Remove Cluster B').click()
        page.get_by_role('button',name='Remove Cluster C').click()
        import pandas as pd
        hist=pd.read_csv(Path(__file__).resolve().parents[1]/'dashboard_data/historical_hub_week.csv')
        expected=int(hist.loc[hist.cluster.eq('Cluster A'),'orders'].sum())
        expect(page.locator('[data-testid="stMetricValue"]').first).to_have_text(f'{expected:,}')
        evidence['checks'].append(f'Cluster A selection matches {expected:,} historical orders')
        with page.expect_download() as dl:
            page.get_by_role('button',name='Download dashboard source').click()
        download=dl.value; download.save_as(output/'CarryBee-Dashboard-Source.zip')
        with zipfile.ZipFile(output/'CarryBee-Dashboard-Source.zip') as z:
            names=z.namelist(); assert 'app.py' in names
            assert not any(n.startswith(('data/','outputs/','.git/')) or n.endswith(('.sqlite3','.db','.env')) for n in names)
        evidence['checks'].append('Browser source download: explicit safe contents')
        for view,title in [('overview','Executive Overview'),('hubs','Hub Diagnostics'),('forecast','Forecast and Budget')]:
            page.close(); page=browser.new_page(viewport={'width':1200,'height':1000})
            page.goto(url+'?view='+view,wait_until='networkidle')
            plots=page.locator('[data-testid="stPlotlyChart"] .js-plotly-plot'); plots.first.wait_for()
            values=plots.evaluate_all('els => els.map(el => ({traces:el.data.map(t=>({name:t.name,type:t.type,points:t.x?.length||t.y?.length||0})),legend:el.layout.showlegend, xTitle:el.layout.xaxis?.title?.text,yTitle:el.layout.yaxis?.title?.text}))')
            assert len(values)==2
            assert all(c['traces'] for c in values)
            evidence['chart_traces'][view]=values
            main=page.locator('[data-testid="stMain"]')
            height=main.evaluate('el=>el.scrollHeight'); viewport=main.evaluate('el=>el.clientHeight')
            for i,offset in enumerate(range(0,int(height),int(viewport)-70),1):
                main.evaluate('(el,n)=>el.scrollTop=n',offset)
                page.wait_for_timeout(250)
                main.screenshot(path=str(output/f'report-{view}-{i:02}.png'),animations='disabled')
        browser.close()
    (output/'interaction-verification.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print(json.dumps(evidence,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8503/');parser.add_argument('--output',type=Path,default=Path('outputs/dashboard/screenshots'))
    a=parser.parse_args();verify(a.url,a.output)
