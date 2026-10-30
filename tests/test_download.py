import pytest

from src.download_data import validate_csv, download_all


@pytest.mark.parametrize("payload,content_type", [
    (b"<html>Access denied</html>", "text/html"), (b"<!DOCTYPE html>Sign in", ""),
    (b"", "text/csv"), (b"wrong,header\n1,2\n", "text/csv"),
    (b"hub_id,hub_name,cluster\n", "text/csv"), (b"hub_id,hub_name,cluster\nH1,Name\n", "text/csv"),
    (b"hub_id,hub_name,cluster\nH1,Name,Cluster,EXTRA\n", "text/csv"),
    (b"hub_id,hub_name,cluster\nH1,Name,\x00\n", "text/csv"),
])
def test_reject_invalid_csv(payload, content_type):
    with pytest.raises(ValueError):
        validate_csv(payload, "hubs", content_type)


def test_utf8_bom_and_quoted_comma():
    assert validate_csv(b'\xef\xbb\xbfhub_id,hub_name,cluster\nH1,"Hub, One",C1\n', "hubs") == 1


def test_failed_force_download_preserves_existing_file(tmp_path, monkeypatch):
    from src import download_data

    payload = b"hub_id,hub_name,cluster\nH1,Original,C1\n"
    (tmp_path / "hubs.csv").write_bytes(payload)
    class Response:
        headers = {"Content-Type": "text/html"}
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def raise_for_status(self): pass
        def iter_content(self, size): yield b"<html>Sign in</html>"
    class Session:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def mount(self, *args): pass
        def get(self, *args, **kwargs): return Response()
    monkeypatch.setattr(download_data.requests, "Session", Session)
    monkeypatch.setattr(download_data, "FILE_IDS", {"hubs": "fixture"})
    with pytest.raises(RuntimeError, match="signed-in browser"):
        download_all(tmp_path, force=True)
    assert (tmp_path / "hubs.csv").read_bytes() == payload
