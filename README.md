# HookAPI

Signed webhook receiver: accept HMAC-SHA256–signed POSTs, store raw payloads in SQLite, list/inspect events, and replay original bodies to a configured downstream URL.

## Install

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Configure & run

Demo config lives at `configs/demo.yaml`. It resolves the shared secret from the environment:

```yaml
hmac_secret: ${HOOKAPI_HMAC_SECRET}
```

**Set the secret before starting uvicorn.** The module-level `app` in `hookapi/api.py` loads `configs/demo.yaml` (or the path in `HOOKAPI_CONFIG`) at import time via `create_app(load_config(...))`. If `HOOKAPI_HMAC_SECRET` is missing, config load fails and uvicorn serves an empty placeholder app with no webhook routes.

```bash
export HOOKAPI_HMAC_SECRET='dev-secret-change-me'
# optional: export HOOKAPI_CONFIG=/absolute/path/to/config.yaml
uvicorn hookapi.api:app --host 127.0.0.1 --port 8000
```

For tests and custom wiring, prefer the factory:

```python
from hookapi.api import create_app
from hookapi.config import load_config

app = create_app(load_config("configs/demo.yaml"))
```

## Sign a request (Python)

Header format: `X-Hookapi-Signature: sha256=<lowercase hex>` (HMAC-SHA256 of the **raw** body bytes).

```python
import hashlib
import hmac

secret = "dev-secret-change-me"
body = b'{"hello":"world"}'
digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
header = f"sha256={digest}"
print(header)  # X-Hookapi-Signature value
```

## Local demo (curl)

Receive a signed webhook:

```bash
export HOOKAPI_HMAC_SECRET='dev-secret-change-me'
BODY='{"hello":"world"}'
SIG=$(python - <<'PY'
import hashlib, hmac, os
body = b'{"hello":"world"}'
secret = os.environ["HOOKAPI_HMAC_SECRET"]
print("sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest())
PY
)

curl -sS -X POST "http://127.0.0.1:8000/hooks/demo" \
  -H "Content-Type: application/json" \
  -H "X-Hookapi-Signature: $SIG" \
  -d "$BODY"
```

Expected: HTTP `201` with `{ "id", "source", "received_at" }`. Missing or bad signature → `401` (nothing stored).

List recent events (optional `?source=` filter):

```bash
curl -sS "http://127.0.0.1:8000/events"
curl -sS "http://127.0.0.1:8000/events?source=demo"
```

Inspect one event:

```bash
curl -sS "http://127.0.0.1:8000/events/<EVENT_ID>"
```

Replay the stored raw body to `forward_url` from config (demo default: `http://127.0.0.1:9999/sink`):

```bash
curl -sS -X POST "http://127.0.0.1:8000/events/<EVENT_ID>/replay"
```

## Tests

Offline pytest (no live network; replay uses mocked httpx):

```bash
pytest
```

## Portfolio (Upwork)

**Title:** Signed Webhook Receiver (FastAPI + SQLite Replay)

**Description:** Accept HMAC-SHA256–signed POSTs, store raw payloads in SQLite, list/inspect events, and replay original bodies to a configured downstream URL. Includes offline tests and a clear local demo for clients verifying webhook integrations.
