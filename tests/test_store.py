from pathlib import Path

from hookapi.store import Event, EventStore


def test_insert_get_list_update_replay(tmp_path: Path):
    db = tmp_path / "events.db"
    store = EventStore(db)

    headers = {
        "content-type": "application/json",
        "x-hookapi-signature": "sha256=" + ("ab" * 32),
    }
    body = b'{"hello":"world"}'
    event = store.insert("github", body, headers)

    assert isinstance(event, Event)
    assert event.id
    assert event.source == "github"
    assert event.received_at.endswith("Z") or "+" in event.received_at or event.received_at.endswith("+00:00")
    assert event.body == body
    assert event.headers == headers
    assert event.replay_status == "none"
    assert event.replay_detail is None

    loaded = store.get(event.id)
    assert loaded is not None
    assert loaded.id == event.id
    assert loaded.body == body
    assert loaded.headers == headers
    assert loaded.replay_status == "none"

    assert store.get("missing-id") is None

    other = store.insert("stripe", b"other", {"content-type": "text/plain"})
    listed = store.list_events(limit=50)
    assert {e.id for e in listed} == {event.id, other.id}

    filtered = store.list_events(source="github")
    assert [e.id for e in filtered] == [event.id]

    store.update_replay(event.id, "ok", "200 OK")
    updated = store.get(event.id)
    assert updated is not None
    assert updated.replay_status == "ok"
    assert updated.replay_detail == "200 OK"

    store.update_replay(event.id, "failed", "connection refused")
    failed = store.get(event.id)
    assert failed is not None
    assert failed.replay_status == "failed"
    assert failed.replay_detail == "connection refused"
