# HookAPI Design

**Date:** 2026-11-03  
**Goal:** A small, installable FastAPI service that receives signed webhooks, stores events in SQLite, and can replay them to a configured downstream URL — for an Upwork portfolio demo.

## Purpose

Show clients we can ship webhook ingestion services: accept POSTs, verify HMAC-SHA256 signatures, persist payloads, list/inspect events, and replay original bodies to a downstream HTTP endpoint. Targets fixed-price Upwork jobs like “webhook receiver / FastAPI integration / signature verification.”

## Non-goals (v1)

- OAuth, multi-tenant auth UI, dashboards
- Redis / background workers / queues
- Bearer-token auth (HMAC only for v1)
- PostgreSQL or cloud DBs (SQLite only for demo)
- Mutual TLS, IP allowlists
- Transforming or mutating payloads on replay (forward original raw body)

## Approach (approved)

Small installable package (`pip install -e .`) with FastAPI app, YAML/env config, SQLite event store, HMAC-SHA256 header verification, HTTP forwarder for replay, pytest with TestClient + mocked downstream HTTP. Same packaging style as ScrapePack / AlertWatch.

## Architecture

```
configs/demo.yaml     secret, db path, optional default forward_url
hookapi/
  config.py           Load/validate settings (Pydantic)
  verify.py           HMAC-SHA256 over raw body; constant-time compare
  store.py            SQLite events table
  forward.py          POST raw body to downstream URL
  api.py              FastAPI routes
  __init__.py
tests/                Offline unit + API tests; httpx mocked for replay
```

**Data flow:** POST `/hooks/{source}` → read raw body → verify `X-Hookapi-Signature: sha256=<hex>` → insert event → `201` with id.  
`POST /events/{id}/replay` → load event → POST original body (+ optional original content-type) to configured `forward_url` → update replay status.

## Config shape (v1)

- `hmac_secret`: shared secret (support `${ENV}` placeholders; never commit real secrets)
- `database_path`: SQLite path (default `./data/hookapi.db`)
- `forward_url`: default downstream URL for replay (required for replay endpoint when not overridden)
- `host` / `port`: bind defaults for local demo docs only (uvicorn still started explicitly)

## HTTP API

| Method | Path | Behavior |
|--------|------|----------|
| `POST` | `/hooks/{source}` | Accept raw body; require `X-Hookapi-Signature: sha256=<hex>` (HMAC-SHA256 of raw bytes with `hmac_secret`). Invalid/missing → `401`. Success → store event, return `201` `{ "id", "source", "received_at" }`. |
| `GET` | `/events` | List recent events (id, source, received_at, replay_status); optional `?source=` filter. |
| `GET` | `/events/{id}` | Single event metadata + body (UTF-8 text if decodable, else base64 flag). |
| `POST` | `/events/{id}/replay` | POST stored raw body to `forward_url`. Downstream HTTP errors → mark `replay_failed`, return error detail; original event kept. Success → `replay_ok`. |

Signature header format is fixed for v1: `X-Hookapi-Signature: sha256=<lowercase hex>`.

## Storage

SQLite table `events`:

- `id` TEXT PRIMARY KEY (UUID)
- `source` TEXT
- `received_at` TEXT (UTC ISO)
- `headers_json` TEXT (subset: content-type + signature header only)
- `body_blob` BLOB
- `replay_status` TEXT (`none` / `ok` / `failed`)
- `replay_detail` TEXT NULL

## Error handling

- Missing or bad signature → `401`, nothing stored
- Unknown event id → `404`
- Replay without configured `forward_url` → `400`
- Downstream failure on replay → event retained; `replay_status=failed`; response includes status/error text

## Testing

- Offline pytest: HMAC pass/fail, store round-trip, list/get, replay with mocked httpx (no live network)
- FastAPI `TestClient` for route-level checks
- No Playwright / Selenium

## Success criteria

1. Fresh clone: venv, `pip install -e ".[dev]"`, start uvicorn, curl signed POST → `201` and row in SQLite
2. Replay to a mocked/local URL updates status; failure path leaves event intact
3. pytest green offline
4. English README: install, sign example (openssl/python), receive, list, replay, env secret, Upwork portfolio blurb

## Portfolio copy (draft)

**Title:** Signed Webhook Receiver (FastAPI + SQLite Replay)  
**Description:** Accept HMAC-SHA256–signed POSTs, store raw payloads in SQLite, list/inspect events, and replay original bodies to a configured downstream URL. Includes offline tests and a clear local demo for clients verifying webhook integrations.

## Global constraints

- Repo root: `/workspace/hookapi`
- Package / import name: `hookapi`
- Python 3.11+, FastAPI, uvicorn, pydantic v2, httpx, pyyaml, pytest
- English README (Upwork portfolio)
- Secrets only via config `${ENV}` or env; never commit real tokens
