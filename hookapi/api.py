"""FastAPI routes for HookAPI webhook ingestion and replay."""

from __future__ import annotations

import base64
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from hookapi.config import AppConfig, load_config
from hookapi.forward import forward_raw
from hookapi.store import Event, EventStore
from hookapi.verify import (
    compute_signature,
    parse_signature_header,
    signatures_match,
)

SIGNATURE_HEADER = "X-Hookapi-Signature"


def create_app(config: AppConfig) -> FastAPI:
    app = FastAPI(title="HookAPI")
    store = EventStore(config.database_path)

    @app.post("/hooks/{source}", status_code=201)
    async def receive_hook(source: str, request: Request):
        body = await request.body()
        sig_header = request.headers.get(SIGNATURE_HEADER)
        provided = parse_signature_header(sig_header)
        if provided is None:
            raise HTTPException(status_code=401, detail="missing or invalid signature header")
        expected = compute_signature(config.hmac_secret, body)
        if not signatures_match(expected, provided):
            raise HTTPException(status_code=401, detail="invalid signature")

        headers_subset: dict[str, str] = {}
        content_type = request.headers.get("content-type")
        if content_type is not None:
            headers_subset["content-type"] = content_type
        if sig_header is not None:
            headers_subset["x-hookapi-signature"] = sig_header

        event = store.insert(source, body, headers_subset)
        return {
            "id": event.id,
            "source": event.source,
            "received_at": event.received_at,
        }

    @app.get("/events")
    def list_events(source: str | None = Query(default=None)):
        events = store.list_events(source=source)
        return [_event_summary(e) for e in events]

    @app.get("/events/{event_id}")
    def get_event(event_id: str):
        event = store.get(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="event not found")
        return _event_detail(event)

    @app.post("/events/{event_id}/replay")
    def replay_event(event_id: str):
        if not config.forward_url:
            raise HTTPException(status_code=400, detail="forward_url is not configured")
        event = store.get(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="event not found")

        content_type = event.headers.get("content-type")
        try:
            status, text = forward_raw(
                config.forward_url,
                event.body,
                content_type=content_type,
            )
        except httpx.HTTPError as exc:
            detail = str(exc)
            store.update_replay(event_id, "failed", detail)
            return JSONResponse(
                status_code=502,
                content={
                    "id": event_id,
                    "replay_status": "failed",
                    "detail": detail,
                },
            )

        if 200 <= status < 300:
            store.update_replay(event_id, "ok", f"{status} {text}"[:500])
            return {
                "id": event_id,
                "replay_status": "ok",
                "downstream_status": status,
                "detail": text,
            }

        store.update_replay(event_id, "failed", f"{status} {text}"[:500])
        return JSONResponse(
            status_code=502,
            content={
                "id": event_id,
                "replay_status": "failed",
                "downstream_status": status,
                "detail": text,
            },
        )

    return app


def _event_summary(event: Event) -> dict:
    return {
        "id": event.id,
        "source": event.source,
        "received_at": event.received_at,
        "replay_status": event.replay_status,
    }


def _event_detail(event: Event) -> dict:
    payload: dict = {
        "id": event.id,
        "source": event.source,
        "received_at": event.received_at,
        "headers": event.headers,
        "replay_status": event.replay_status,
        "replay_detail": event.replay_detail,
    }
    try:
        text = event.body.decode("utf-8")
        payload["body"] = text
        payload["body_encoding"] = "utf-8"
        payload["body_is_base64"] = False
    except UnicodeDecodeError:
        payload["body"] = base64.b64encode(event.body).decode("ascii")
        payload["body_encoding"] = "base64"
        payload["body_is_base64"] = True
    return payload


# Module-level app for `uvicorn hookapi.api:app`.
# Prefer create_app(config) in tests. Import must stay safe without secret env:
# configs/demo.yaml uses ${HOOKAPI_HMAC_SECRET}; if unset, keep a placeholder.
app = FastAPI(title="HookAPI")
_config_path = os.environ.get("HOOKAPI_CONFIG", "configs/demo.yaml")
if Path(_config_path).is_file():
    try:
        app = create_app(load_config(_config_path))
    except (KeyError, ValueError, OSError):
        # Secret missing or invalid config at import time — placeholder remains.
        pass
