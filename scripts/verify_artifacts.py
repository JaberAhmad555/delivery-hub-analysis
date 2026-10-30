"""Validate final PDFs, extracted SQL, PPTX chart values and shared finances."""
import hashlib
import json
import re
import sqlite3
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
from pandas.testing import assert_frame_equal
from pypdf import PdfReader
from src.config import ROOT,DB

def verify():
    folder=ROOT/'outputs/final'
    report=folder/'CarryBee_Assessment_DRAFT.pdf'
    reader=PdfReader(report)
    texts=[p.extract_text() for p in reader.pages]
    assert all('DRAFT - NOT FOR SUBMISSION' in t for t in texts)
    text='\n'.join(texts)
    clean='\n'.join(line for line in text.splitlines() if not line.startswith(('CarryBee |','Private assessment review |','Page ')))
    count=0
    with sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True) as con:
        for file in sorted((ROOT/'sql').glob('q[1-7]_*.sql')):
            match=re.search(r'BEGIN SQL: '+re.escape(file.name)+r'\n(.*?)END SQL: '+re.escape(file.name),clean,re.S)
            assert match, file.name
            sections=re.split(r'^-- result: (\w+)\s*$',match.group(1),flags=re.M)
            for name,sql in zip(sections[1::2],sections[2::2]):
                assert_frame_equal(pd.read_sql_query(sql,con),pd.read_csv(ROOT/'outputs'/f'{name}.csv'),check_dtype=False)
                count+=1
    assert count==8
    pptx=folder/'CarryBee_Management_Presentation.pptx'
    ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main','c':'http://schemas.openxmlformats.org/drawingml/2006/chart'}
    f=json.loads((folder/'verified_facts.json').read_text())
    with zipfile.ZipFile(pptx) as z:
        slides=sorted(n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n))
        charts=sorted(n for n in z.namelist() if re.fullmatch(r'ppt/(?:slides/)?charts/chart\d+\.xml',n))
        assert len(slides)==8 and len(charts)==4
        slide_text='\n'.join(' '.join(ET.fromstring(z.read(n)).itertext()) for n in slides)
        contract=json.loads((ROOT/'outputs/verification/chart_data_contract.json').read_text())
        found=[]
        for name in charts:
            node=ET.fromstring(z.read(name))
            for series in node.findall('.//c:ser',ns):
                values=[float(v.text) for v in series.findall('./c:val//c:pt/c:v',ns)]
                found.append(values)
        expected=[s['values'] for c in contract for s in c['series']]
        assert sorted(found)==sorted(expected)
        # Independently reconstruct the chart contracts from the shared source facts.
        reference=[]
        reference += [[h[k] for k in ['attempts','delivered','holds','returned']] for h in f['history']]
        reference += [[h['historical_util'] for h in f['hubs']]]
        reference += [[h['agent_side_holds'] for h in f['hold_reasons']], [h['total_holds']-h['agent_side_holds'] for h in f['hold_reasons']]]
        reference += [[w['baseline_max_util'] for w in f['weekly']],[w['after_max_util'] for w in f['weekly']],[.85]*4]
        assert sorted(found)==sorted([[round(v,6) for v in a] for a in reference])
        assert len([n for n in z.namelist() if n.startswith('ppt/embeddings/') and n.endswith('.xlsx')])==4
    for value in ['65,400','4,600','17,140.65','48,259.35','62,800','25,076.09','185,600','73.79']:
        assert value in slide_text,('slide',value)
        assert value in text,('report',value)
    assert f['recommended']['budget_reserved_bdt']==65400
    for name,digest in f['source_hashes'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest, name
    slide_pdf=PdfReader(folder/'CarryBee_Management_Presentation.pdf')
    assert len(slide_pdf.pages)==8
    assert all(len(p.images)==1 for p in slide_pdf.pages)
    files=[report,pptx,folder/'CarryBee_Management_Presentation.pdf']
    result={'assessment_pages':len(reader.pages),'presentation_slides':len(slides),'presentation_pdf_pages':len(slide_pdf.pages),
            'extracted_sql_result_sets_executed_and_matched':count,'native_charts_verified':len(charts),
            'native_chart_series_verified':len(found),'embedded_chart_workbooks':4,'financial_text_consistency':'passed',
            'source_hashes_verified':len(f['source_hashes']),'draft_label_on_every_report_page':True,
            'slide_pdf_format':'faithful raster companion; editable native objects in PPTX',
            'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files}}
    assert all(v['bytes']>10000 for v in result['files'].values())
    (ROOT/'outputs/verification/artifact-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (ROOT/'outputs/verification/report-extracted-text.txt').write_text(text,encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':verify()
