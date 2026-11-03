from pathlib import Path
from hookapi.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO = REPO_ROOT / "configs" / "demo.yaml"

def test_load_demo_config(monkeypatch):
    monkeypatch.setenv("HOOKAPI_HMAC_SECRET", "test-secret")
    cfg = load_config(DEMO)
    assert cfg.hmac_secret == "test-secret"
    assert cfg.database_path.name == "hookapi.db"
    assert cfg.forward_url == "http://127.0.0.1:9999/sink"
