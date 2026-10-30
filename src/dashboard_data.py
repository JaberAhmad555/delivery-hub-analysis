"""Read-only aggregate snapshot loader shared by the app and clean-start tests."""
import hashlib
import json
from pathlib import Path
from io import BytesIO
import zipfile

import pandas as pd


def load_snapshot(path: Path | None = None) -> tuple[dict, dict]:
    path = path or Path(__file__).resolve().parents[1] / "dashboard_data"
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    if not metadata["phase1_validated"] or not metadata["phase1_unchanged"]:
        raise ValueError("Snapshot is not based on verified Phase 1 outputs")
    tables = {}
    for filename, expected in metadata["files"].items():
        file = path / filename
        if hashlib.sha256(file.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError(f"Snapshot checksum mismatch: {filename}")
        frame = pd.read_csv(file)
        if len(frame) != expected["rows"]:
            raise ValueError(f"Snapshot row-count mismatch: {filename}")
        tables[file.stem] = frame
    return tables, metadata


def dashboard_source_zip(root: Path | None = None) -> bytes:
    """Share only the self-contained app and approved snapshot, via an allowlist."""
    root = root or Path(__file__).resolve().parents[1]
    names = ["app.py", "requirements.txt", ".streamlit/config.toml", "src/__init__.py", "src/dashboard_data.py"]
    names += [str(p.relative_to(root)) for p in sorted((root / "dashboard_data").glob("*")) if p.is_file()]
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in names:
            path = root / name
            archive.write(path, path.relative_to(root).as_posix())
        archive.writestr("RUN.md", "# CarryBee dashboard\n\nPython 3.13. Install with `python -m pip install -r requirements.txt`, "
                         "then run `python -m streamlit run app.py`. The included aggregate snapshot is sufficient; no raw data, "
                         "database or secrets are needed. Agent labels are pseudonyms.\n")
    return buffer.getvalue()
