"""Export a faithful eight-page PDF companion from genuine rendered slide PNGs.

Editable text, charts, tables and embedded data are in the PPTX. The PDF is the
visual companion; its pages are rendered images, unlike the selectable report.
"""
import argparse
from pathlib import Path
from reportlab.pdfgen import canvas

def build(render_dir,destination):
    files=sorted(Path(render_dir).glob('slide-*.png'))
    if len(files)!=8: raise ValueError('Exactly eight verified slide renders required')
    c=canvas.Canvas(str(destination),pagesize=(960,540))
    c.setTitle('CarryBee Management Presentation - Review Draft')
    for file in files:
        c.drawImage(str(file),0,0,width=960,height=540); c.showPage()
    c.save()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('render_dir');p.add_argument('destination');a=p.parse_args();build(a.render_dir,a.destination)
