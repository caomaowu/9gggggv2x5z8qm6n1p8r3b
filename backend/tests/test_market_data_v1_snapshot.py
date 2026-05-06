"""
V1 snapshot tests for MarketDataService.

These tests capture the **current** behaviour of ``market_data.py`` so any
future refactoring (e.g. v5 migration) can be validated against this baseline.

ALL HTTP calls are mocked – no real network traffic is involved.
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock

from app.services.market_data import MarketDataService


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_empty_ohlcv_get():
    """Return a session.get side_effect that produces empty OHLCV data."""

    def _get(url, params=None, headers=None, timeout=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"status": "success", "data": []}
        return resp

    return _get


def _make_error_ohlcv_get():
    """Return a session.get side_effect that produces an error status."""

    def _get(url, params=None, headers=None, timeout=None, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"status": "error", "msg": "something wrong"}
        return resp

    return _get


# ── Tests ────────────────────────────────────────────────────────────────────

class TestGetOhlcvData:
    """Snapshot tests for get_ohlcv_data."""

    def test_get_ohlcv_data_basic(self, mock_requests_session):
        """
        Fetch BTC 1h data → expect a DataFrame with Date index and
        Open/High/Low/Close/Volume columns.
        """
        svc = MarketDataService()
        df = svc.get_ohlcv_data("BTC", "1h")

        assert df is not None, "Expected a DataFrame, got None"
        assert isinstance(df, pd.DataFrame), f"Expected DataFrame, got {type(df)}"
        assert not df.empty, "DataFrame should not be empty"

        assert df.index.name == "Date", f"Index name should be 'Date', got '{df.index.name}'"
        assert isinstance(df.index, pd.DatetimeIndex), f"Expected DatetimeIndex, got {type(df.index)}"

        expected_cols = {"Open", "High", "Low", "Close", "Volume"}
        actual_cols = set(df.columns)
        missing = expected_cols - actual_cols
        assert not missing, f"Missing columns: {missing}"

        assert len(df) == 2, f"Expected 2 rows, got {len(df)}"

    def test_get_ohlcv_data_empty(self, mock_requests_session):
        """Empty data array → expect None."""
        mock_requests_session.get.side_effect = _make_empty_ohlcv_get()

        svc = MarketDataService()
        df = svc.get_ohlcv_data("BTC", "1h")

        assert df is None, f"Expected None for empty data, got {type(df)}"

    def test_get_ohlcv_data_error(self, mock_requests_session):
        """Error status in response → expect None (graceful handling)."""
        mock_requests_session.get.side_effect = _make_error_ohlcv_get()

        svc = MarketDataService()
        df = svc.get_ohlcv_data("BTC", "1h")

        # Current behaviour: _make_request retries and then raises Exception,
        # which is caught by get_ohlcv_data → returns None.
        assert df is None, f"Expected None on error, got {type(df)}"


class TestHealth:
    """Snapshot tests for check_health."""

    def test_check_health_success(self, mock_requests_session):
        """Health endpoint returns success → expect healthy with response_time."""
        svc = MarketDataService()
        result = svc.check_health()

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result["status"] == "healthy", f"Expected 'healthy', got {result['status']}"
        assert "response_time" in result, "Missing 'response_time' key"
        assert isinstance(result["response_time"], float), (
            f"response_time should be float, got {type(result['response_time'])}"
        )
        assert result["response_time"] >= 0, "response_time should be non-negative"


class TestExchanges:
    """Snapshot tests for get_exchanges."""

    def test_get_exchanges(self, mock_requests_session):
        """Get exchanges list → must contain 'okx'."""
        svc = MarketDataService()
        exchanges = svc.get_exchanges()

        assert isinstance(exchanges, list), f"Expected list, got {type(exchanges)}"
        assert "okx" in exchanges, f"'okx' not found in exchanges: {exchanges}"


class TestLatestPrice:
    """Snapshot tests for get_latest_price."""

    def test_get_latest_price(self, mock_requests_session):
        """Fetch latest BTC price → expect correct float from last Close."""
        svc = MarketDataService()
        price = svc.get_latest_price("BTC")

        assert price is not None, "Expected a float price, got None"
        assert isinstance(price, float), f"Expected float, got {type(price)}"
        # The mock data has close=2.0 for the last (second) row
        assert price == 2.0, f"Expected 2.0, got {price}"
