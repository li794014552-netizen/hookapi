"""HTTP forwarder for replaying stored webhook bodies."""

from __future__ import annotations

import httpx


def forward_raw(
    url: str,
    body: bytes,
    *,
    content_type: str | None = None,
) -> tuple[int, str]:
    """POST *body* to *url*.

    Returns ``(status_code, response_text)`` for any HTTP response, including
    non-2xx. Does **not** call ``raise_for_status``.

    Raises:
        httpx.HTTPError: on transport / connection failures (no response).
    """
    headers: dict[str, str] = {}
    if content_type is not None:
        headers["Content-Type"] = content_type

    response = httpx.post(url, content=body, headers=headers)
    return response.status_code, response.text
