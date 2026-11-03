"""HMAC-SHA256 signature helpers for webhook verification."""

from __future__ import annotations

import hashlib
import hmac


def compute_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def parse_signature_header(header: str | None) -> str | None:
    if header is None:
        return None
    prefix = "sha256="
    if not header.startswith(prefix):
        return None
    digest = header[len(prefix) :]
    if not digest:
        return None
    return digest


def signatures_match(expected_hex: str, provided_hex: str) -> bool:
    return hmac.compare_digest(expected_hex, provided_hex)
