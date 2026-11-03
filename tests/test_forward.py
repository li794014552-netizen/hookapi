from unittest.mock import MagicMock, patch

import httpx
import pytest

from hookapi.forward import forward_raw


def test_forward_raw_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "ok"

    with patch("hookapi.forward.httpx.post", return_value=mock_response) as mock_post:
        status, text = forward_raw(
            "http://example.com/sink",
            b'{"a":1}',
            content_type="application/json",
        )

    assert status == 200
    assert text == "ok"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://example.com/sink"
    assert kwargs["content"] == b'{"a":1}'
    assert kwargs["headers"]["Content-Type"] == "application/json"


def test_forward_raw_non_2xx_returns_status_without_raising():
    mock_response = MagicMock()
    mock_response.status_code = 502
    mock_response.text = "bad gateway"

    with patch("hookapi.forward.httpx.post", return_value=mock_response):
        status, text = forward_raw("http://example.com/sink", b"body")

    assert status == 502
    assert text == "bad gateway"


def test_forward_raw_connection_error_raises():
    with patch(
        "hookapi.forward.httpx.post",
        side_effect=httpx.ConnectError("connection refused"),
    ):
        with pytest.raises(httpx.HTTPError):
            forward_raw("http://example.com/sink", b"body")
