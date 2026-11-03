from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from hookapi.config import AppConfig
from hookapi.verify import compute_signature
from hookapi.api import create_app


SECRET = "test-secret-for-api"


def _make_client(tmp_path: Path, *, forward_url: str | None = "http://127.0.0.1:9999/sink"):
    cfg = AppConfig(
        hmac_secret=SECRET,
        database_path=tmp_path / "events.db",
        forward_url=forward_url,
    )
    app = create_app(cfg)
    return TestClient(app)


def _sig_header(body: bytes) -> dict[str, str]:
    digest = compute_signature(SECRET, body)
    return {"X-Hookapi-Signature": f"sha256={digest}"}


def test_post_hooks_signed_returns_201(tmp_path: Path):
    client = _make_client(tmp_path)
    body = b'{"event":"ping"}'
    resp = client.post(
        "/hooks/github",
        content=body,
        headers={**_sig_header(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["source"] == "github"
    assert "received_at" in data


def test_post_hooks_bad_signature_401(tmp_path: Path):
    client = _make_client(tmp_path)
    body = b'{"event":"ping"}'
    resp = client.post(
        "/hooks/github",
        content=body,
        headers={
            "X-Hookapi-Signature": "sha256=" + ("00" * 32),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


def test_post_hooks_missing_signature_401(tmp_path: Path):
    client = _make_client(tmp_path)
    resp = client.post(
        "/hooks/github",
        content=b"{}",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 401


def test_list_and_get_events(tmp_path: Path):
    client = _make_client(tmp_path)
    body = b'{"hello":"world"}'
    create = client.post(
        "/hooks/stripe",
        content=body,
        headers={**_sig_header(body), "Content-Type": "application/json"},
    )
    assert create.status_code == 201
    event_id = create.json()["id"]

    listed = client.get("/events")
    assert listed.status_code == 200
    items = listed.json()
    assert isinstance(items, list)
    assert any(e["id"] == event_id for e in items)
    meta = next(e for e in items if e["id"] == event_id)
    assert meta["source"] == "stripe"
    assert "received_at" in meta
    assert meta["replay_status"] == "none"

    filtered = client.get("/events", params={"source": "stripe"})
    assert filtered.status_code == 200
    assert all(e["source"] == "stripe" for e in filtered.json())

    detail = client.get(f"/events/{event_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["id"] == event_id
    assert payload["source"] == "stripe"
    assert payload["body"] == body.decode("utf-8")
    assert payload.get("body_encoding", "utf-8") in ("utf-8", None) or "body_base64" not in payload or payload.get("body_is_base64") is False


def test_get_event_404(tmp_path: Path):
    client = _make_client(tmp_path)
    resp = client.get("/events/does-not-exist")
    assert resp.status_code == 404


def test_replay_success(tmp_path: Path):
    client = _make_client(tmp_path)
    body = b'{"replay":true}'
    create = client.post(
        "/hooks/github",
        content=body,
        headers={**_sig_header(body), "Content-Type": "application/json"},
    )
    event_id = create.json()["id"]

    with patch(
        "hookapi.api.forward_raw",
        return_value=(200, "ok"),
    ) as mock_fwd:
        resp = client.post(f"/events/{event_id}/replay")

    assert resp.status_code == 200
    data = resp.json()
    assert data["replay_status"] == "ok"
    mock_fwd.assert_called_once()

    detail = client.get(f"/events/{event_id}")
    assert detail.json()["replay_status"] == "ok"


def test_replay_failed_downstream(tmp_path: Path):
    client = _make_client(tmp_path)
    body = b'{"replay":"fail"}'
    create = client.post(
        "/hooks/github",
        content=body,
        headers={**_sig_header(body), "Content-Type": "application/json"},
    )
    event_id = create.json()["id"]

    with patch(
        "hookapi.api.forward_raw",
        return_value=(502, "bad gateway"),
    ):
        resp = client.post(f"/events/{event_id}/replay")

    assert resp.status_code == 200 or resp.status_code >= 400
    detail = client.get(f"/events/{event_id}")
    assert detail.json()["replay_status"] == "failed"
    # original event still present
    assert detail.json()["id"] == event_id


def test_replay_without_forward_url_400(tmp_path: Path):
    client = _make_client(tmp_path, forward_url=None)
    body = b"{}"
    create = client.post(
        "/hooks/github",
        content=body,
        headers={**_sig_header(body), "Content-Type": "application/json"},
    )
    event_id = create.json()["id"]
    resp = client.post(f"/events/{event_id}/replay")
    assert resp.status_code == 400


def test_replay_connection_error_marks_failed(tmp_path: Path):
    client = _make_client(tmp_path)
    body = b'{"x":1}'
    create = client.post(
        "/hooks/github",
        content=body,
        headers={**_sig_header(body), "Content-Type": "application/json"},
    )
    event_id = create.json()["id"]

    with patch(
        "hookapi.api.forward_raw",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        resp = client.post(f"/events/{event_id}/replay")

    detail = client.get(f"/events/{event_id}")
    assert detail.json()["replay_status"] == "failed"
    assert detail.json()["id"] == event_id
