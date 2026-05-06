# V5 OHLCV candle response column order (first row is header strings, rest are string values)
V5_KLINE_COLUMNS = ["ts", "o", "h", "l", "c", "vol", "volCcy", "volCcyQuote", "confirm"]

# Timeframe mapping: v1 (lowercase) → v5 OKX (mixed case for hours/days/weeks/months)
TIMEFRAME_V1_TO_V5 = {
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

# OKX v5 API success code
V5_SUCCESS_CODE = "0"
