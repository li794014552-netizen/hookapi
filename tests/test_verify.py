import hashlib
import hmac

from hookapi.verify import compute_signature, parse_signature_header, signatures_match


def test_compute_signature_lowercase_hex():
    secret = "test-secret"
    body = b'{"ok":true}'
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert compute_signature(secret, body) == expected
    assert compute_signature(secret, body) == expected.lower()
    assert not compute_signature(secret, body).startswith("sha256=")


def test_signatures_match_good_and_bad():
    secret = "test-secret"
    body = b"payload"
    good = compute_signature(secret, body)
    assert signatures_match(good, good) is True
    assert signatures_match(good, "0" * 64) is False


def test_parse_signature_header():
    hex_digest = "a" * 64
    assert parse_signature_header(f"sha256={hex_digest}") == hex_digest
    assert parse_signature_header(f"sha256={hex_digest.upper()}") == hex_digest.upper()
    assert parse_signature_header(None) is None
    assert parse_signature_header("") is None
    assert parse_signature_header("md5=deadbeef") is None
    assert parse_signature_header(hex_digest) is None
