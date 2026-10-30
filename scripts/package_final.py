"""Create a private review ZIP and a separate public-safe dashboard source ZIP."""
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from src.config import ROOT
from src.dashboard_data import dashboard_source_zip

def package():
    review=ROOT/'outputs/review';review.mkdir(parents=True,exist_ok=True)
    archive=review/'CarryBee-Final-Review.zip'
    source=review/'CarryBee-Dashboard-Source.zip'; source.write_bytes(dashboard_source_zip())
    files=set()
    for pattern in ['*.md','requirements*.txt','.gitignore','.gitattributes','pytest.ini','app.py','.streamlit/config.toml',
                    'src/*.py','sql/*.sql','tests/*.py','scripts/*.py','scripts/*.mjs',
                    'dashboard_data/*.csv','dashboard_data/*.json','dashboard_data/*.md',
                    'outputs/q*.csv','outputs/results.md','outputs/validation.json','outputs/run_manifest.json',
                    'outputs/final-pytest*','outputs/strategic/*.csv','outputs/strategic/*.json','outputs/strategic/*.md',
                    'outputs/dashboard/screenshots/*.png','outputs/dashboard/screenshots/*.json',
                    'outputs/dashboard/clean-environment/*.json','outputs/verification/*.json','outputs/verification/*.txt',
                    'outputs/final/*.pdf','outputs/final/*.pptx','outputs/final/*.json','outputs/final/slide_renders/*.png']:
        files.update(p for p in ROOT.glob(pattern) if p.is_file())
    # Explicitly retain the original Phase 1 documentation, but no original input files.
    manifest={p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)}
    forbidden=('.sqlite','.sqlite3','.db','.env','.zip','.pyc')
    assert not any(n.startswith(('data/','.git/','.venv/')) or n.endswith(forbidden) for n in manifest)
    assert all('secrets' not in n.lower() for n in manifest)
    commits=subprocess.check_output(['git','log','-6','--format=%H %s'],cwd=ROOT,text=True)
    manifest_path=review/'package-manifest.json'
    manifest_path.write_text(json.dumps({'files':manifest,'local_commits':commits.splitlines()},indent=2),encoding='utf-8')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):z.write(p,p.relative_to(ROOT).as_posix())
        z.write(manifest_path,'PACKAGE_MANIFEST.json')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(files)+1
        for name,info in manifest.items():
            assert hashlib.sha256(z.read(name)).hexdigest()==info['sha256']
    result={'archive':archive.name,'bytes':archive.stat().st_size,'file_count':len(files)+1,
            'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'crc_and_content_hashes':'passed',
            'excluded':'original datasets, databases, credentials, virtual environments, Git internals and nested archives',
            'source_zip':{'name':source.name,'bytes':source.stat().st_size}}
    (review/'package-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':package()
