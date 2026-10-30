"""Package code, reviewed strategy outputs and genuine screenshots; no raw data."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

import sys
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import ROOT, OUTPUTS
from src.dashboard_data import dashboard_source_zip
from src.scenario_analysis import phase1_hashes


def package():
    destination = OUTPUTS / "review"
    destination.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((OUTPUTS / "strategic" / "scenario_manifest.json").read_text(encoding="utf-8"))
    if phase1_hashes() != manifest["phase1_sha256"]:
        raise ValueError("Phase 1 hashes changed")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()
    state = {"commits": git("log", "-5", "--format=%H %s").splitlines(), "branch": git("branch", "--show-current"),
             "working_tree": git("status", "--porcelain"), "remote": git("remote", "-v"), "phase1_unchanged": True}
    (destination / "git-status.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (destination / "CarryBee-Phase2-dashboard-source.zip").write_bytes(dashboard_source_zip())
    paths = []
    for folder in ["src", "sql", "tests", "scripts", "dashboard_data"]:
        paths.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    for filename in ["app.py", "requirements.txt", "requirements-dev.txt", "pytest.ini", ".gitignore", ".gitattributes",
                     "README.md", "ASSUMPTIONS.md", "REVIEW_HANDOFF.md", "PHASE2_HANDOFF.md", "DEPLOYMENT.md", ".streamlit/config.toml"]:
        paths.append(ROOT / filename)
    for folder in ["strategic", "dashboard/screenshots"]:
        paths.extend(p for p in (OUTPUTS / folder).rglob("*") if p.is_file())
    for filename in ["phase2-pytest-output.txt", "phase2-pytest-results.xml", "clean-environment-verification.json", "phase2-verification.json"]:
        if (OUTPUTS / filename).exists():
            paths.append(OUTPUTS / filename)
    paths.append(destination / "git-status.json")
    archive = destination / "CarryBee-Phase2-review.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(set(paths)):
            relative = path.relative_to(ROOT)
            if any(part in {".git", ".venv", "raw", "__pycache__"} for part in relative.parts) or path.suffix in {".sqlite", ".sqlite3", ".db", ".zip"}:
                raise ValueError(f"Excluded file in package: {relative}")
            bundle.write(path, (Path("CarryBee-Analytics") / relative).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise ValueError("Archive validation failed")
    return {"archive": str(archive), "bytes": archive.stat().st_size, "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "files": len(paths), "phase1_unchanged": True}


if __name__ == "__main__":
    print(json.dumps(package(), indent=2))

