"""Build shared verified facts and a reproducible, selectable-text assessment PDF.

Default is always DRAFT. Final mode needs a public URL and matching successful
anonymous-browser evidence produced by verify_dashboard.py.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Preformatted, Image, KeepTogether

ROOT=Path(__file__).resolve().parents[1]
TEAL=colors.HexColor('#087F79'); INK=colors.HexColor('#143638')

def final_allowed(url, evidence):
    if not url: return False
    from urllib.parse import urlparse
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.hostname in {'localhost','127.0.0.1'}:
        raise ValueError('Final report requires an actual HTTPS public dashboard URL')
    data=json.loads(Path(evidence).read_text(encoding='utf-8')) if evidence else {}
    checks=data.get('checks',[])
    if data.get('url','').rstrip('/')!=url.rstrip('/') or data.get('javascript_errors')!=[] or len([x for x in checks if x.get('http_status')==200])!=3:
        raise ValueError('Successful anonymous three-page browser evidence is required')
    return True

def wrap_sql(sql,width=105):
    """Wrap only outside quoted literals; preserve SQL comments and semantics."""
    lines=[]
    for line in sql.splitlines():
        if line.lstrip().startswith('--'):
            import textwrap
            lines.extend(textwrap.wrap(line.strip()[2:].strip(),width-3,initial_indent='-- ',subsequent_indent='-- ',break_long_words=False,break_on_hyphens=False) or ['--'])
            continue
        while len(line)>width:
            quote=None; safe=[]
            for i,c in enumerate(line[:width+1]):
                if c in "'\"":
                    if quote==c: quote=None
                    elif quote is None: quote=c
                if c==' ' and quote is None: safe.append(i)
            if not safe: break
            cut=safe[-1]; lines.append(line[:cut]); line='    '+line[cut:].lstrip()
        lines.append(line)
    return '\n'.join(lines)

def facts(root=ROOT):
    def read(name,base='outputs/strategic'): return pd.read_csv(root/base/(name+'.csv'))
    scenarios=read('scenario_comparison'); weekly=read('weekly_staffing_plan')
    rec=scenarios[scenarios.scenario.str.startswith('Recommended')].iloc[0]
    base=scenarios.iloc[0]
    rw=weekly[weekly.scenario==rec.scenario]
    bw=weekly[weekly.scenario==base.scenario]
    hist=read('historical_hub_week','dashboard_data')
    forecast=read('q7_staffing_forecast','outputs')
    network=[]
    for week,g in rw.groupby('forecast_week'):
        b=bw[bw.forecast_week==week]
        network.append({'week':int(week),'orders':g.forecast_orders.sum(),'baseline_attempts':g.baseline_attempts.sum(),
            'after_attempts':g.required_attempts_after_programme.sum(),'baseline_target_capacity':g.baseline_target_capacity.sum(),
            'target_capacity':g.target_capacity.sum(),'baseline_max_util':g.baseline_utilisation.max(),
            'after_max_util':g.projected_utilisation.max(),'baseline_target_queue':b.planning_backlog_week_end.sum(),
            'after_target_queue':g.planning_backlog_week_end.sum(),'hard_queue':g.hard_backlog_week_end.sum(),
            'savings_bdt':g.hold_cost_savings_bdt.sum()})
    hubs=[]
    eight=json.loads(scenarios[scenarios.scenario=='Eight fixed hires'].iloc[0]['plan'])['hires']
    for hub,g in rw.groupby('hub_id',sort=True):
        h=hist[(hist.hub_id==hub)&(hist.week==2)].iloc[0]
        first=g.iloc[0]; n=eight[hub]
        hubs.append({'hub':first.hub_name,'cluster':first.cluster,'current':int(first.existing_agents),
            'peak_required':int(forecast[forecast.hub_id==hub].required_agents.max()),
            'hires':int(first.new_hires),'net_transfer':int(first.net_transfers),'roster':int(first.roster_agents),
            'programme':bool(first.programme),'historical_util':float(h.utilisation),
            'eight_hire_allocation':n,'eight_hire_cost_bdt':n*23200})
    history=[]
    for week,g in hist.groupby('week'):
        entry={'week':int(week)}
        for c in ['orders','attempts','delivered','holds','returned','operating_cost_bdt']: entry[c]=float(g[c].sum())
        entry['cost_per_delivery']=entry['operating_cost_bdt']/entry['delivered']
        for c in ['delivered','holds','returned']: entry[c+'_rate']=entry[c]/entry['attempts']
        history.append(entry)
    result={'recommended':rec.fillna('').to_dict(),'baseline':base.fillna('').to_dict(),'weekly':network,'hubs':hubs,'history':history,
        'scenarios':scenarios.fillna('').to_dict('records'),'budget':read('budget_allocation').to_dict('records'),
        'hold_reasons':read('q3_hold_reasons','outputs').to_dict('records'),
        'source_hashes':{str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in list((root/'outputs/strategic').glob('*.csv'))+list((root/'outputs').glob('q*.csv'))}}
    return result

def build(url=None,evidence=None):
    final=final_allowed(url,evidence); out=ROOT/'outputs/final'; out.mkdir(parents=True,exist_ok=True)
    f=facts(); (out/'verified_facts.json').write_text(json.dumps(f,indent=2,allow_nan=False,default=lambda v:v.item()),encoding='utf-8')
    pd.DataFrame(f['hubs']).to_csv(ROOT/'outputs/strategic/q8_hub_decisions.csv',index=False)
    styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BodyX',fontName='Helvetica',fontSize=9.2,leading=13,spaceAfter=7,textColor=INK))
    styles.add(ParagraphStyle(name='SmallX',fontName='Helvetica',fontSize=7.3,leading=9.3,textColor=INK))
    styles.add(ParagraphStyle(name='CodeX',fontName='Courier',fontSize=7.4,leading=9.4,textColor=INK,spaceAfter=10))
    for name in ['Title','Heading1','Heading2','Heading3']: styles[name].textColor=TEAL
    story=[]
    def p(text,style='BodyX'): return Paragraph(escape(str(text)).replace('\n','<br/>'),styles[style])
    def add(text,style='BodyX'): story.append(p(text,style))
    def heading(text): add(text,'Heading1')
    def fmt(v):
        if pd.isna(v): return '-'
        if isinstance(v,float): return f'{v:,.4f}'.rstrip('0').rstrip('.')
        return str(v)
    def table(frame,caption=None):
        if caption: add(caption,'Heading3')
        # Split wide results horizontally, repeating identifying fields in each part.
        columns=list(frame.columns)
        keys=[c for c in (['day','agent_id'] if 'agent_id' in columns else ['hub_name','week','week_start']) if c in columns]
        keys=keys[:2] or columns[:1]
        rest=[c for c in columns if c not in keys]
        parts=[columns] if len(columns)<=7 else [keys+rest[i:i+5] for i in range(0,len(rest),5)]
        for ix,cols in enumerate(parts):
            if len(parts)>1: add(f'Columns {ix+1} of {len(parts)} (same rows and keys)','SmallX')
            rows=[[p(c.replace('_',' '),'SmallX') for c in cols]]
            rows += [[p(fmt(v),'SmallX') for v in row] for row in frame[cols].itertuples(index=False,name=None)]
            t=Table(rows,colWidths=[511/len(cols)]*len(cols),repeatRows=1,hAlign='LEFT')
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DDEEEB')),('VALIGN',(0,0),(-1,-1),'TOP'),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F4F7F6')]),('LINEBELOW',(0,0),(-1,0),.6,TEAL),
                ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            story.extend([t,Spacer(1,10)])
    add('CARRYBEE EXPRESS','Heading2'); add('Operations analytics\nTechnical assessment','Title')
    add('FINAL SUBMISSION' if final else 'DRAFT - NOT FOR SUBMISSION','Heading1')
    add('Prepared for the Head of Operations | 31 October 2026')
    add('Historical evidence: 13-26 October 2026. Forecast: 27 October-23 November 2026.')
    add('Decision: transfer two experienced fixed-salary agents from Lakeview to Greenfield; hire two fixed-salary agents at Hillcrest; run the Riverside hold programme.')
    add('Reserve BDT 65,400; retain BDT 4,600. Projected first-28-day hold-charge savings: BDT 17,140.65. This is a service-led recommendation, with negative whole-package first-month cash ROI.')
    add('Public dashboard: '+url if final else 'PUBLIC DASHBOARD PENDING. This draft is not submission-ready. The owner must publish the app, verify anonymous access and supply the actual URL.')
    add('Contents','Heading2'); add('Task 1: methodology, all seven SQL queries and required results.\nTask 2: Q8-Q10 staffing, budget, forecasts, benefits, sensitivities and risks.\nTask 3: genuine dashboard screenshots and deployment status.\nTask 4: separate eight-slide management presentation.\nAppendix: original assumptions and reproducibility.')
    add('The source assessment is a three-page brief; it does not impose a three-page response limit. This report includes complete selectable SQL and readable results. Private review copy: contains required derived agent-level SQL results. Do not publish this report or review archive with the public app.','SmallX')
    story.append(PageBreak()); heading('Task 1 | SQL assessment')
    add('Methodology and verified scope','Heading2')
    add('Eight supplied tables contain 22,789 orders, 51,190 event logs, 64 agents (62 currently active), six hubs, two salary rules, five cost rules, eight operational rules and 24 forecast records. All 25,595 Assigned attempt events match exactly one Delivered, Hold or Returned outcome. The daily roster includes 882 eligible agent-days, including 28 zero-activity days.')
    add('An attempt is an Assigned event, not every log row. Week 1 is 13-19 October; Week 2 is 20-26 October. Historical event rates use attempts as the denominator; final-status order rates shown in the dashboard use newly created orders. Two inactive agents remain eligible through 19 October. Salaries use eligible paid days, including zero-attempt days. Forecast workload is new orders multiplied by Week 2 attempts per new order; staffing is CEILING(attempts / (7 x 40 x 85%)).')
    add('SQL dialect: SQLite with window functions and recursive CTEs. Queries execute independently against the supplied schema. Monetary values are BDT. Ratios in SQL results are fractions (multiply by 100 for percentages). Displayed decimals are rounded; CSVs preserve precision. Each result has been independently reconciled against Python references and original data.')
    sql_files=sorted((ROOT/'sql').glob('q[1-7]_*.sql'))
    result_files={1:['q1_first20','q1_hub_summary'],2:['q2_utilisation'],3:['q3_hold_reasons'],4:['q4_held_orders'],5:['q5_high_return_agents'],6:['q6_delivery_costs'],7:['q7_staffing_forecast']}
    for i,file in enumerate(sql_files,1):
        story.append(PageBreak()); heading(f'Q{i} | '+file.stem[3:].replace('_',' ').title())
        add('BEGIN SQL: '+file.name,'SmallX')
        story.append(Preformatted(wrap_sql(file.read_text(encoding='utf-8')),styles['CodeX']))
        add('END SQL: '+file.name,'SmallX')
        for name in result_files[i]: table(pd.read_csv(ROOT/'outputs'/f'{name}.csv'),name.replace('_',' ').title())
        if i==1: add('The daily result is intentionally limited here to its required first 20 rows. The full 882-row result is supplied as q1_agent_day.csv; the complete hub summary is above.')
    story.append(PageBreak()); heading('Task 2 | Strategic analysis')
    add('Q8 | Hub-by-hub decision on the eight-hire request','Heading2')
    table(pd.DataFrame(f['hubs'])[['hub','current','peak_required','eight_hire_allocation','eight_hire_cost_bdt','hires','net_transfer','roster']])
    add('The employer did not specify the eight-hire split. A marginal planning-queue allocation assigns three to Greenfield, two to Riverside and three to Hillcrest. At BDT 23,200 each (5,000 recruitment plus 28 x 650 pay), eight fixed hires cost BDT 185,600, exceeding the budget by BDT 115,600. Lakeview, Brookside and Westwood need no hires in any baseline forecast week. Greenfield has a two-agent peak gap filled by transfer. Hillcrest has a two-agent persistent gap filled by selective hiring. Riverside has a two-agent baseline peak gap, but its unusually large controllable hold burden supports a programme under the available budget; monitor its residual target breaches closely.')
    add('Lakeview and Greenfield are both Cluster A. Lakeview Week 2 utilisation is 56.17%, strictly below the 75% donor rule. Removing two leaves nine agents, above its peak requirement of eight. Brookside qualifies at 71.49% in Cluster C but Westwood has no projected gap. Riverside and Hillcrest cannot donate. New Hillcrest staff produce 60% for their first seven days but receive full pay. Proposed rosters by hub: 12, 9, 12, 11, 11 and 9 respectively; network total 64.')
    add('Sensitivity summary: the same plan costs BDT 62,800 under 26 paid days. A linear hold ramp produces BDT 25,076.09 in projected hold-charge savings, versus BDT 17,140.65 in the conservative delayed-effect base case. The recommendation uses the 28-day reserve and delayed base, not these more favourable assumptions.')
    # Preserve the complete strategic narrative and its tabular numerical evidence.
    md=(ROOT/'outputs/strategic/STRATEGIC_ANALYSIS.md').read_text(encoding='utf-8')
    lines=md.splitlines(); i=0
    while i<len(lines):
        line=lines[i]
        if line.startswith('|'):
            block=[]
            while i<len(lines) and lines[i].startswith('|'): block.append(lines[i]); i+=1
            cells=[[v.strip() for v in x.strip('|').split('|')] for x in block]
            table(pd.DataFrame(cells[2:],columns=cells[0])); continue
        if line.startswith('## '):
            story.append(PageBreak()); add(line[3:],'Heading2')
        elif line.startswith('### '): add(line[4:],'Heading3')
        elif line and not line.startswith('# '): add(line.removeprefix('- '))
        i+=1
    add('Four-week network comparison','Heading2'); table(pd.DataFrame(f['weekly']))
    story.append(PageBreak()); heading('Task 3 | Interactive operations dashboard')
    add('Public URL: '+url if final else 'Deployment status: pending owner publication. No publicly accessible dashboard URL has been verified. DRAFT - NOT FOR SUBMISSION.')
    add('Run from the project directory: .\\.venv\\Scripts\\python.exe -m streamlit run app.py. The deployment-ready app reads only the aggregate snapshot. Sidebar navigation exposes Executive Overview, Hub Diagnostics, and Forecast and Budget. Historical cluster/period filters and the hub selector update historical figures. Forecast charts cover all four weeks, and scenario cards show network-wide BDT costs. Historical and projected values are explicitly labelled. The source download excludes raw employer data, SQLite, secrets and review archives.')
    add('The following images are actual Chromium screenshots of the rendered app, not mock-ups. Full-resolution whole-page screenshots and browser check evidence are included in the review package. The report uses consecutive viewport captures for legibility; overlapping content reflects real scrolling.')
    for view,title in [('overview','Executive Overview'),('hubs','Hub Diagnostics'),('forecast','Forecast and Budget')]:
        captures=sorted((ROOT/'outputs/dashboard/screenshots').glob(f'report-{view}-*.png'))
        if not captures: raise ValueError('Run verify_interactions before generating report screenshots')
        for n,file in enumerate(captures,1):
            story.append(PageBreak()); heading(f'{title} | view {n} of {len(captures)}')
            image=Image(str(file)); scale=min(511/image.imageWidth,665/image.imageHeight)
            image.drawWidth=image.imageWidth*scale; image.drawHeight=image.imageHeight*scale; story.append(image)
    story.append(PageBreak()); heading('Appendix | Assumptions and reproducibility')
    add('The following Phase 1 notes are preserved from the original milestone. Their original scope paragraph described future work at that time; Tasks 2-4 are now completed in this draft, with public deployment still pending. The app is implemented and no longer a placeholder.')
    notes=(ROOT/'ASSUMPTIONS.md').read_text(encoding='utf-8').splitlines(); i=0
    while i<len(notes):
        line=notes[i]
        if line.startswith('|'):
            block=[]
            while i<len(notes) and notes[i].startswith('|'): block.append(notes[i]); i+=1
            cells=[[v.strip() for v in x.strip('|').split('|')] for x in block]
            table(pd.DataFrame(cells[2:],columns=cells[0])); continue
        if line.startswith('#'): add(line.lstrip('# '),'Heading3')
        elif line: add(line.removeprefix('- '))
        i+=1
    add('Reproduction','Heading2'); add('See TECHNICAL_HANDOFF.md for the source-of-truth files, verification commands, artifact generation and public-link finalization. See outputs/verification and final-pytest-results.xml for executed checks. Phase 1 SQL and CSV hashes are preserved in scenario_manifest.json. Financial report and presentation inputs share verified_facts.json. Source records are excluded from all sharing archives.')
    def page(canvas,doc):
        canvas.saveState(); canvas.setFont('Helvetica',8); canvas.setFillColor(INK)
        canvas.drawString(42,817,'CarryBee | '+('Assessment' if final else 'DRAFT - NOT FOR SUBMISSION'))
        canvas.drawRightString(553,24,f'Page {doc.page}'); canvas.drawString(42,24,'Private assessment review | BDT throughout'); canvas.restoreState()
    destination=out/('CarryBee_Assessment_FINAL.pdf' if final else 'CarryBee_Assessment_DRAFT.pdf')
    SimpleDocTemplate(str(destination),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=44,bottomMargin=43,title='CarryBee assessment - '+('Final' if final else 'DRAFT - NOT FOR SUBMISSION'),author='CarryBee Analytics').build(story,onFirstPage=page,onLaterPages=page)
    print(destination)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--public-url'); parser.add_argument('--verification')
    args=parser.parse_args(); build(args.public_url,args.verification)
