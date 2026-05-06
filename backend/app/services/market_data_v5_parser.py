"""
market_data_v5_parser.py — Pure functions for parsing OKX v5 API responses.

Converts v5 candle/response formats into the DataFrame shape expected by the
existing MarketDataService (Date‑indexed, columns: Open/High/Low/Close/Volume).
"""

from __future__ import annotations

import pandas as pd
from typing import Any

# ---------------------------------------------------------------------------
# Inline fallback constants (used when the constants module is unavailable)
# ---------------------------------------------------------------------------
_V5_KLINE_COLUMNS = ["ts", "o", "h", "l", "c", "vol", "volCcy", "volCcyQuote", "confirm"]
_V5_SUCCESS_CODE = "0"

_INLINE_TIMEFRAME_V1_TO_V5: dict[str, str] = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "6h": "6H",
    "12h": "12H",
    "1d": "1D",
    "1w": "1W",
    "1mo": "1M",
    "3mo": "3M",
}


# ===================================================================
# 1.  is_v5_success
# ===================================================================
def is_v5_success(response_json: dict[str, Any] | None) -> bool:
    """Return True when the response carries OKX v5 success code ``"0"``."""
    if response_json is None:
        return False
    return response_json.get("code") == "0"


# ===================================================================
# 2.  get_v5_data
# ===================================================================
def get_v5_data(response_json: dict[str, Any] | None) -> list[Any] | dict[str, Any] | None:
    """Extract the *data* field from a v5 response.

    Returns ``None`` when the field is missing.  An existing but empty
    list / dict is returned as-is — the caller decides how to handle it.
    """
    if response_json is None:
        return None
    return response_json.get("data")


# ===================================================================
# 3.  parse_v5_ohlcv_to_dataframe
# ===================================================================
def parse_v5_ohlcv_to_dataframe(
    response_json: dict[str, Any] | None,
) -> pd.DataFrame | None:
    """Convert a v5 candle response into a standardised OHLCV DataFrame.

    The returned DataFrame has:
        * index  → ``Date`` (datetime, sorted ascending)
        * columns → ``Open``, ``High``, ``Low``, ``Close``, ``Volume`` (float64)

    OKX v5 candle format (NO header row, position-based):
        [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]

    Returns ``None`` on any parse / data error.
    """
    # --- guard ------------------------------------------------
    if not is_v5_success(response_json):
        return None

    data = get_v5_data(response_json)
    if data is None or not isinstance(data, list) or len(data) == 0:
        return None

    # Check if first row is a string header (docs format) or actual data (real API)
    # Real API returns data rows directly without header
    first_row = data[0]
    if isinstance(first_row, list) and len(first_row) > 0 and isinstance(first_row[0], str) and not first_row[0].isdigit():
        # Header row present (documentation format)
        header = first_row
        body = data[1:]
        if not body:
            return None
    else:
        # No header row (real API format) — use position-based column names
        header = ["ts", "o", "h", "l", "c", "vol", "volCcy", "volCcyQuote", "confirm"]
        body = data

    # --- build DataFrame --------------------------------------
    try:
        df = pd.DataFrame(body, columns=header)
    except (ValueError, TypeError):
        return None

    if df.empty:
        return None

    # --- column transforms ------------------------------------

    # ts → datetime index named "Date"
    if "ts" in df.columns:
        df["ts"] = pd.to_numeric(df["ts"], errors="coerce")
        df["Date"] = pd.to_datetime(df["ts"], unit="ms", errors="coerce")
        df = df.drop(columns=["ts"], errors="ignore")
    else:
        return None  # ts column is mandatory

    # Drop rows where Date could not be parsed
    df = df.dropna(subset=["Date"])

    # If all dates were invalid, stop
    if df.empty:
        return None

    # Rename o/h/l/c → Open/High/Low/Close
    _rename_map = {"o": "Open", "h": "High", "l": "Low", "c": "Close", "vol": "Volume"}
    for old, new in _rename_map.items():
        if old in df.columns:
            df = df.rename(columns={old: new})

    # --- numeric conversion (coerce invalid values to NaN) ----
    numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
        else:
            # Column missing entirely → fill with NaN so shape stays consistent
            df[col] = float("nan")

    # --- cleanup ----------------------------------------------
    df = df.drop(columns=["volCcy"], errors="ignore")

    # Keep only the standard columns
    keep_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in df.columns]
    df = df.set_index("Date")[keep_cols]

    df = df.sort_index()

    return df


# ===================================================================
# 4.  convert_timeframe_v1_to_v5
# ===================================================================
def convert_timeframe_v1_to_v5(tf: str) -> str:
    """Map a v1-style timeframe string to its v5 equivalent.

    Falls back to the original string when no mapping is found.
    """
    try:  # pragma: no cover — constants module exists in the repo
        from .market_data_v5_constants import TIMEFRAME_V1_TO_V5 as _MAPPING
    except ImportError:  # pragma: no cover
        _MAPPING = _INLINE_TIMEFRAME_V1_TO_V5

    return _MAPPING.get(tf, tf)


# ===================================================================
# 5.  convert_symbol_for_v5
# ===================================================================
def convert_symbol_for_v5(symbol: str, inst_type: str = "SWAP") -> str:
    """Normalise a human-readable symbol into an OKX v5 instrument ID.

    Rules (applied in order):
        1. Replace ``/`` with ``-``.
        2. Uppercase everything.
        3. If the result already ends with ``-SWAP`` or ``-SPOT``, return as-is.
        4. If it ends with ``-USDT`` (but not ``-USDT-SWAP`` / ``-USDT-SPOT``),
           append ``-{inst_type}``.
        5. If there is **no** ``-`` in the symbol, append ``-USDT-{inst_type}``.
        6. Otherwise return the symbol unchanged.

    Parameters
    ----------
    symbol : str
        e.g. ``"BTC"``, ``"ETH/USDT"``, ``"BTC-USDT-SWAP"``.
    inst_type : str
        Instrument type suffix (``"SWAP"`` or ``"SPOT"``).  Default ``"SWAP"``.
    """
    symbol = (symbol or "").strip()

    # 1. Replace "/" with "-"
    if "/" in symbol:
        symbol = symbol.replace("/", "-")

    # 2. Uppercase
    symbol = symbol.upper()

    if not symbol:
        return symbol

    # 2.5 Handle bare USDT suffix (e.g. "DOGEUSDT" → "DOGE-USDT")
    if symbol.endswith("USDT") and len(symbol) > 4 and "-" not in symbol:
        base = symbol[:-4]
        symbol = f"{base}-USDT"

    # 3. Already complete
    if symbol.endswith("-SWAP") or symbol.endswith("-SPOT"):
        return symbol

    # 4. Ends with -USDT but not yet fully qualified
    if symbol.endswith("-USDT"):
        return f"{symbol}-{inst_type}"

    # 5. Bare symbol (no separator)
    if "-" not in symbol:
        return f"{symbol}-USDT-{inst_type}"

    # 6. Fallthrough — e.g. "BTC-ETH" stays as-is
    return symbol


# ===================================================================
# 6.  build_v5_ohlcv_params
# ===================================================================
def build_v5_ohlcv_params(
    instId: str,
    bar: str,
    limit: int = 100,
    after: int | None = None,
    before: int | None = None,
) -> dict[str, Any]:
    """Build the query-parameter dict for the v5 ``/market/candles`` endpoint.

    Only keys with **non-None** values are included in the returned dict.
    """
    params: dict[str, Any] = {
        "instId": instId,
        "bar": bar,
        "limit": limit,
    }
    if after is not None:
        params["after"] = after
    if before is not None:
        params["before"] = before
    return params
