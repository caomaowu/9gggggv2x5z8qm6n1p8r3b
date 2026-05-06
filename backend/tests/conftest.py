import pytest
from unittest.mock import MagicMock


# ── Standalone data fixtures (for reference / reuse) ──────────────────────────

@pytest.fixture
def mock_v1_response():
    """Realistic v1 OHLCV response with timestamp-based records."""
    return {
        "status": "success",
        "data": [
            {"timestamp": 1764921600000, "open": 1.5, "high": 2.0, "low": 1.0, "close": 1.8, "volume": 1000},
            {"timestamp": 1764943200000, "open": 1.8, "high": 2.2, "low": 1.6, "close": 2.0, "volume": 1500},
        ],
    }


@pytest.fixture
def mock_v1_error_response():
    """V1 error response payload."""
    return {"status": "error", "msg": "something wrong"}


@pytest.fixture
def mock_v5_response():
    """Realistic v5 candles response (array-of-arrays format with header)."""
    return {
        "code": "0",
        "msg": "",
        "data": [
            ["ts", "o", "h", "l", "c", "vol", "volCcy"],
            ["1764921600000", "1.5", "2.0", "1.0", "1.8", "1000", "1500"],
            ["1764943200000", "1.8", "2.2", "1.6", "2.0", "1500", "2700"],
        ],
    }


@pytest.fixture
def mock_v5_error_response():
    """V5 error response payload."""
    return {"code": "1", "msg": "error message", "data": []}


# ── Autouse HTTP mock ────────────────────────────────────────────────────────

def _default_v1_ohlcv():
    return {
        "status": "success",
        "data": [
            {"timestamp": 1764921600000, "open": 1.5, "high": 2.0, "low": 1.0, "close": 1.8, "volume": 1000},
            {"timestamp": 1764943200000, "open": 1.8, "high": 2.2, "low": 1.6, "close": 2.0, "volume": 1500},
        ],
    }


def _default_get(url, params=None, headers=None, timeout=None, **kwargs):
    """Default side_effect for session.get – dispatches on URL path."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.status_code = 200

    url_str = url if isinstance(url, str) else str(url)

    if "/api/v1/ohlcv" in url_str:
        resp.json.return_value = _default_v1_ohlcv()
    elif "/api/v1/healthz" in url_str:
        resp.json.return_value = {"status": "success"}
    elif "/api/v1/exchanges" in url_str:
        # exchanges endpoint returns a plain list (handled by isinstance(data, list) in _make_request)
        resp.json.return_value = ["okx", "binance", "bybit"]
    elif "/api/v5/" in url_str:
        resp.json.return_value = {
            "code": "0",
            "msg": "",
            "data": [
                ["ts", "o", "h", "l", "c", "vol", "volCcy"],
                ["1764921600000", "1.5", "2.0", "1.0", "1.8", "1000", "1500"],
                ["1764943200000", "1.8", "2.2", "1.6", "2.0", "1500", "2700"],
            ],
        }
    else:
        resp.json.return_value = {"status": "success"}

    return resp


@pytest.fixture(autouse=True)
def mock_requests_session(monkeypatch):
    """
    Replace requests.Session with a mock so **no real network calls** happen.

    Returns the mock session instance so individual tests can override its
    ``.get.side_effect`` to simulate empty / error / edge-case responses.
    """
    import requests as req_module

    mock_session = MagicMock()
    mock_session.mount = MagicMock()          # needed by MarketDataService.__init__
    mock_session.get.side_effect = _default_get

    monkeypatch.setattr(req_module, "Session", lambda: mock_session)

    return mock_session
