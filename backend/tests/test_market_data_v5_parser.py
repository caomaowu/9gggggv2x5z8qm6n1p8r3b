"""
Unit tests for market_data_v5_parser.py — pure functions, no network.
"""
import pandas as pd
import pytest

from app.services.market_data_v5_parser import (
    is_v5_success,
    get_v5_data,
    parse_v5_ohlcv_to_dataframe,
    convert_timeframe_v1_to_v5,
    convert_symbol_for_v5,
    build_v5_ohlcv_params,
)

# ---------------------------------------------------------------------------
# Shared test fixtures / samples
# ---------------------------------------------------------------------------

# Documentation format (with header row)
SAMPLE_V5_CANDLES = {
    "code": "0",
    "msg": "",
    "data": [
        ["ts", "o", "h", "l", "c", "vol", "volCcy"],
        ["1764921600000", "1.5", "2.0", "1.0", "1.8", "1000", "1500"],
        ["1764943200000", "1.8", "2.2", "1.6", "2.0", "1500", "2700"],
    ],
}

# Real API format (no header row, 9-element rows)
SAMPLE_V5_CANDLES_REAL = {
    "code": "0",
    "msg": "",
    "data": [
        ["1764921600000", "1.5", "2.0", "1.0", "1.8", "1000", "1500", "1350", "1"],
        ["1764943200000", "1.8", "2.2", "1.6", "2.0", "1500", "2700", "2400", "1"],
    ],
}

SAMPLE_V5_ERROR = {"code": "1", "msg": "Operation failed", "data": []}

SAMPLE_V5_HEADER_ONLY = {
    "code": "0",
    "msg": "",
    "data": [["ts", "o", "h", "l", "c", "vol", "volCcy"]],
}

SAMPLE_V5_EMPTY_DATA = {"code": "0", "msg": "", "data": []}

SAMPLE_V5_NO_DATA_KEY = {"code": "0", "msg": ""}

SAMPLE_V5_BAD_TS = {
    "code": "0",
    "msg": "",
    "data": [
        ["ts", "o", "h", "l", "c", "vol", "volCcy"],
        ["not_a_number", "1.0", "2.0", "0.5", "1.5", "100", "200"],
    ],
}

SAMPLE_V5_PARTIAL_NUMERIC = {
    "code": "0",
    "msg": "",
    "data": [
        ["ts", "o", "h", "l", "c", "vol", "volCcy"],
        ["1764921600000", "bad", "", "0.5", "N/A", "abc", ""],
    ],
}

SAMPLE_V5_MISSING_COLUMNS = {
    "code": "0",
    "msg": "",
    "data": [
        ["ts", "o", "h", "l", "c"],
        ["1764921600000", "1.0", "2.0", "0.5", "1.5"],
    ],
}

SAMPLE_V5_UNSORTED = {
    "code": "0",
    "msg": "",
    "data": [
        ["ts", "o", "h", "l", "c", "vol", "volCcy"],
        ["1764943200000", "1.8", "2.2", "1.6", "2.0", "1500", "2700"],
        ["1764921600000", "1.5", "2.0", "1.0", "1.8", "1000", "1500"],
    ],
}


# ===================================================================
#  is_v5_success
# ===================================================================
class TestIsV5Success:
    def test_success(self):
        assert is_v5_success(SAMPLE_V5_CANDLES) is True

    def test_error_code(self):
        assert is_v5_success(SAMPLE_V5_ERROR) is False

    def test_missing_code(self):
        assert is_v5_success({"msg": "no code"}) is False

    def test_none_input(self):
        assert is_v5_success(None) is False

    def test_integer_code(self):
        """Integer 0 is NOT the string '0' — should be False."""
        assert is_v5_success({"code": 0}) is False


# ===================================================================
#  get_v5_data
# ===================================================================
class TestGetV5Data:
    def test_extracts_data(self):
        data = get_v5_data(SAMPLE_V5_CANDLES)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_error_returns_empty_list(self):
        data = get_v5_data(SAMPLE_V5_ERROR)
        assert data == []  # returned as-is, caller decides

    def test_header_only(self):
        data = get_v5_data(SAMPLE_V5_HEADER_ONLY)
        assert len(data) == 1

    def test_empty_data_returned_as_is(self):
        """An empty ``data`` list is returned as-is (caller decides semantics)."""
        assert get_v5_data(SAMPLE_V5_EMPTY_DATA) == []

    def test_missing_data_key(self):
        assert get_v5_data(SAMPLE_V5_NO_DATA_KEY) is None

    def test_none_input(self):
        assert get_v5_data(None) is None

    def test_data_is_none_explicitly(self):
        assert get_v5_data({"code": "0", "data": None}) is None


# ===================================================================
#  parse_v5_ohlcv_to_dataframe
# ===================================================================
class TestParseV5OhlcvToDataframe:
    # -- happy path ---------------------------------------------------
    def test_success_basic(self):
        df = parse_v5_ohlcv_to_dataframe(SAMPLE_V5_CANDLES)
        assert df is not None
        assert isinstance(df.index, pd.DatetimeIndex)
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]
        assert "volCcy" not in df.columns
        assert len(df) == 2
        assert df["Close"].iloc[-1] == 2.0  # last row close

    def test_dtypes(self):
        df = parse_v5_ohlcv_to_dataframe(SAMPLE_V5_CANDLES)
        assert df["Open"].dtype == "float64"
        assert df["High"].dtype == "float64"
        assert df["Low"].dtype == "float64"
        assert df["Close"].dtype == "float64"
        assert df["Volume"].dtype == "float64"

    def test_sorted_ascending(self):
        """Output index must be sorted chronologically."""
        df = parse_v5_ohlcv_to_dataframe(SAMPLE_V5_UNSORTED)
        assert df.index.is_monotonic_increasing

    # -- error responses ----------------------------------------------
    def test_error_code_returns_none(self):
        assert parse_v5_ohlcv_to_dataframe(SAMPLE_V5_ERROR) is None

    def test_header_only_returns_none(self):
        assert parse_v5_ohlcv_to_dataframe(SAMPLE_V5_HEADER_ONLY) is None

    def test_empty_data_returns_none(self):
        assert parse_v5_ohlcv_to_dataframe(SAMPLE_V5_EMPTY_DATA) is None

    def test_none_input(self):
        assert parse_v5_ohlcv_to_dataframe(None) is None

    def test_missing_ts_column(self):
        resp = {
            "code": "0",
            "data": [
                ["o", "h", "l", "c", "vol"],
                ["1.0", "2.0", "0.5", "1.5", "100"],
            ],
        }
        assert parse_v5_ohlcv_to_dataframe(resp) is None

    # -- edge cases ---------------------------------------------------
    def test_bad_ts_value_skipped(self):
        """Rows with unparseable ts become NaT and are dropped."""
        df = parse_v5_ohlcv_to_dataframe(SAMPLE_V5_BAD_TS)
        assert df is None  # only one row with bad ts → dropped → empty

    def test_partial_numeric_coerces(self):
        """Non-numeric o/h/l/c/vol become NaN via errors='coerce'."""
        df = parse_v5_ohlcv_to_dataframe(SAMPLE_V5_PARTIAL_NUMERIC)
        assert df is not None
        assert len(df) == 1
        # "bad" → NaN, "" → NaN, "N/A" → NaN, "abc" → NaN
        assert pd.isna(df["Open"].iloc[0])
        assert pd.isna(df["High"].iloc[0])
        assert pd.isna(df["Close"].iloc[0])
        assert pd.isna(df["Volume"].iloc[0])
        # valid low should still be numeric
        assert df["Low"].iloc[0] == 0.5

    def test_missing_columns_filled_nan(self):
        """When vol/volCcy columns are missing, Volume becomes NaN."""
        df = parse_v5_ohlcv_to_dataframe(SAMPLE_V5_MISSING_COLUMNS)
        assert df is not None
        assert len(df) == 1
        assert pd.isna(df["Volume"].iloc[0])

    def test_bad_header_not_list(self):
        resp = {
            "code": "0",
            "data": ["not-a-list", ["1764921600000", "1.0"]],
        }
        assert parse_v5_ohlcv_to_dataframe(resp) is None

    def test_volCcy_dropped(self):
        df = parse_v5_ohlcv_to_dataframe(SAMPLE_V5_CANDLES)
        assert "volCcy" not in df.columns

    def test_keep_only_standard_columns(self):
        """Extra columns beyond OHLCV are stripped."""
        resp = {
            "code": "0",
            "data": [
                ["ts", "o", "h", "l", "c", "vol", "volCcy", "extra_col"],
                ["1764921600000", "1.0", "2.0", "0.5", "1.5", "100", "200", "x"],
            ],
        }
        df = parse_v5_ohlcv_to_dataframe(resp)
        assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]


# ===================================================================
#  convert_timeframe_v1_to_v5
# ===================================================================
class TestConvertTimeframeV1ToV5:
    def test_known_mappings(self):
        assert convert_timeframe_v1_to_v5("1h") == "1H"
        assert convert_timeframe_v1_to_v5("4h") == "4H"
        assert convert_timeframe_v1_to_v5("1d") == "1D"
        assert convert_timeframe_v1_to_v5("1w") == "1W"
        assert convert_timeframe_v1_to_v5("1mo") == "1M"
        assert convert_timeframe_v1_to_v5("3mo") == "3M"

    def test_passthrough_minute_tfs(self):
        """Minute timeframes are the same in v5."""
        assert convert_timeframe_v1_to_v5("1m") == "1m"
        assert convert_timeframe_v1_to_v5("5m") == "5m"
        assert convert_timeframe_v1_to_v5("15m") == "15m"

    def test_unknown_returns_original(self):
        assert convert_timeframe_v1_to_v5("unknown") == "unknown"
        assert convert_timeframe_v1_to_v5("2d") == "2d"

    def test_empty_string(self):
        assert convert_timeframe_v1_to_v5("") == ""


# ===================================================================
#  convert_symbol_for_v5
# ===================================================================
class TestConvertSymbolForV5:
    # -- bare symbols ------------------------------------------------
    def test_bare_symbol(self):
        assert convert_symbol_for_v5("BTC") == "BTC-USDT-SWAP"

    def test_bare_symbol_lowercase(self):
        assert convert_symbol_for_v5("btc") == "BTC-USDT-SWAP"

    def test_bare_symbol_with_spaces(self):
        assert convert_symbol_for_v5("  ETH  ") == "ETH-USDT-SWAP"

    # -- slash separators --------------------------------------------
    def test_slash_separator(self):
        assert convert_symbol_for_v5("ETH/USDT") == "ETH-USDT-SWAP"

    def test_slash_separator_lowercase(self):
        assert convert_symbol_for_v5("btc/usdt") == "BTC-USDT-SWAP"

    # -- already dash-separated --------------------------------------
    def test_dash_usdt_needs_inst_type(self):
        assert convert_symbol_for_v5("BTC-USDT") == "BTC-USDT-SWAP"

    def test_dash_usdt_with_spot_type(self):
        assert convert_symbol_for_v5("BTC-USDT", inst_type="SPOT") == "BTC-USDT-SPOT"

    # -- already fully qualified -------------------------------------
    def test_already_swap(self):
        assert convert_symbol_for_v5("BTC-USDT-SWAP") == "BTC-USDT-SWAP"

    def test_already_spot(self):
        assert convert_symbol_for_v5("BTC-USDT-SPOT") == "BTC-USDT-SPOT"

    def test_already_spot_preserve(self):
        """When already -SPOT, changing inst_type should still preserve it."""
        assert convert_symbol_for_v5("BTC-USDT-SPOT", inst_type="SWAP") == "BTC-USDT-SPOT"

    # -- other dash patterns -----------------------------------------
    def test_dash_other_passthrough(self):
        """Symbols like BTC-ETH with no USDT suffix pass through."""
        assert convert_symbol_for_v5("BTC-ETH") == "BTC-ETH"

    def test_ends_with_swap_immediately(self):
        """If symbol ends with -SWAP regardless of prefix, return as-is."""
        assert convert_symbol_for_v5("X-SWAP") == "X-SWAP"

    # -- edge cases --------------------------------------------------
    def test_empty_or_none(self):
        assert convert_symbol_for_v5("") == ""
        # None would fail at .upper(), but empty string is the safe path

    def test_already_spot_with_different_inst_type_keeps_spot(self):
        """Once qualified with -SPOT, the suffix is preserved."""
        assert convert_symbol_for_v5("SOL-USDT-SPOT", inst_type="SWAP") == "SOL-USDT-SPOT"

    def test_usdt_no_dash(self):
        """Symbol that contains USDT without a dash (e.g. USDT itself)."""
        assert convert_symbol_for_v5("USDT") == "USDT-USDT-SWAP"


# ===================================================================
#  build_v5_ohlcv_params
# ===================================================================
class TestBuildV5OhlcvParams:
    def test_minimal_params(self):
        params = build_v5_ohlcv_params("BTC-USDT-SWAP", "1H")
        assert params == {"instId": "BTC-USDT-SWAP", "bar": "1H", "limit": 100}

    def test_with_limit(self):
        params = build_v5_ohlcv_params("BTC-USDT-SWAP", "1H", limit=50)
        assert params["limit"] == 50

    def test_with_after(self):
        params = build_v5_ohlcv_params("BTC-USDT-SWAP", "1H", after=1764921600000)
        assert params["after"] == 1764921600000
        assert "before" not in params

    def test_with_before(self):
        params = build_v5_ohlcv_params("BTC-USDT-SWAP", "1H", before=1765008000000)
        assert params["before"] == 1765008000000
        assert "after" not in params

    def test_with_both_after_and_before(self):
        params = build_v5_ohlcv_params(
            "BTC-USDT-SWAP", "1H",
            after=1764921600000, before=1765008000000,
        )
        assert params["after"] == 1764921600000
        assert params["before"] == 1765008000000

    def test_none_values_excluded(self):
        params = build_v5_ohlcv_params(
            "BTC-USDT-SWAP", "1H", limit=100, after=None, before=None,
        )
        assert "after" not in params
        assert "before" not in params
        assert params == {"instId": "BTC-USDT-SWAP", "bar": "1H", "limit": 100}

    def test_required_keys_present(self):
        params = build_v5_ohlcv_params("ETH-USDT-SWAP", "4H")
        assert "instId" in params
        assert "bar" in params
        assert "limit" in params
