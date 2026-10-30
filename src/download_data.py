"""Download only the supplied CSVs, rejecting HTML and malformed content."""
import argparse
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import FILE_IDS, HEADERS, RAW

MAX_BYTES = 50 * 1024 * 1024


def validate_csv(payload: bytes, table: str, content_type: str = "") -> int:
    if not payload or len(payload) > MAX_BYTES:
        raise ValueError(f"{table}: empty or oversized download")
    text = payload.decode("utf-8-sig")
    prefix = text.lstrip()[:2048].lower()
    if "html" in content_type.lower() or "<html" in prefix or "<!doctype" in prefix or "\x00" in text:
        raise ValueError(f"{table}: response is HTML or binary, not CSV")
    reader = csv.reader(io.StringIO(text), strict=True)
    header = next(reader, [])
    if header != HEADERS[table]:
        raise ValueError(f"{table}: expected headers {HEADERS[table]}, received {header}")
    count = 0
    for line, row in enumerate(reader, 2):
        if len(row) != len(header) or not any(row):
            raise ValueError(f"{table}: malformed/empty record at line {line}")
        count += 1
    if count == 0:
        raise ValueError(f"{table}: no data records")
    return count


def download_all(raw_dir: Path = RAW, force: bool = False) -> dict:
    raw_dir.mkdir(parents=True, exist_ok=True)
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    manifest = {}
    failures = []
    with requests.Session() as session:
        session.mount("https://", HTTPAdapter(max_retries=retry))
        for table, file_id in FILE_IDS.items():
            dest = raw_dir / f"{table}.csv"
            url = f"https://drive.google.com/uc?export=download&id={file_id}"
            try:
                content_type = ""
                if dest.exists() and not force:
                    payload = dest.read_bytes()
                    source = "existing local file (validated; not re-downloaded)"
                else:
                    with session.get(url, timeout=(15, 90), stream=True) as response:
                        response.raise_for_status()
                        content_type = response.headers.get("Content-Type", "")
                        chunks = []
                        size = 0
                        for chunk in response.iter_content(65536):
                            size += len(chunk)
                            if size > MAX_BYTES:
                                raise ValueError(f"{table}: response exceeds {MAX_BYTES} bytes")
                            chunks.append(chunk)
                        payload = b"".join(chunks)
                    source = "downloaded from supplied URL"
                rows = validate_csv(payload, table, content_type)
                if force or not dest.exists():
                    temp = dest.with_suffix(".csv.tmp")
                    temp.write_bytes(payload)
                    temp.replace(dest)
                manifest[table] = {"url": url, "rows": rows, "bytes": len(payload),
                                   "sha256": hashlib.sha256(payload).hexdigest(), "source": source}
                print(f"{table}: {rows:,} rows, CSV validated")
            except (requests.RequestException, ValueError, UnicodeError, csv.Error, OSError) as exc:
                failures.append(f"{table}.csv: {exc}\nOpen {url} in a signed-in browser, download the actual CSV, "
                                f"and save as {dest}. Do not save the web page. Then rerun without --force.")
    (raw_dir / "source_manifest.json").write_text(
        json.dumps({"checked_at_utc": datetime.now(timezone.utc).isoformat(), "files": manifest}, indent=2), encoding="utf-8")
    if failures:
        raise RuntimeError("Downloads incomplete; no substitute data generated.\n" + "\n".join(failures))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    parser.add_argument("--force", action="store_true", help="Re-download, replacing files only after CSV validation")
    args = parser.parse_args()
    try:
        download_all(args.raw_dir, args.force)
    except RuntimeError as exc:
        parser.exit(1, str(exc) + "\n")


if __name__ == "__main__":
    main()
