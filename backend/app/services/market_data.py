import requests
import logging
import time
import pandas as pd
from typing import Dict, Optional, Any, List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.core.config import settings
from app.services.market_data_v5_parser import (
    is_v5_success,
    get_v5_data,
    parse_v5_ohlcv_to_dataframe,
    convert_timeframe_v1_to_v5,
    convert_symbol_for_v5,
    build_v5_ohlcv_params,
)

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Service for fetching market data via OKX v5 transparent proxy.
    Defaults to v5 API with v1 fallback via MARKET_DATA_API_VERSION env var.
    """

    def __init__(self):
        self.base_url = settings.MARKET_DATA_API_URL.rstrip('/')
        self.api_token = settings.MARKET_DATA_API_TOKEN.get_secret_value()
        self.timeout = 15
        self.max_retries = 2

        # API version: "v1" or "v5" (default v5)
        self.api_version = getattr(settings, 'MARKET_DATA_API_VERSION', 'v5')
        self.okx_inst_type = getattr(settings, 'OKX_INSTRUMENT_TYPE', 'SWAP')

        # v1 fallback mappings (kept for backward compat)
        self.symbol_mapping = {"BTC":"BTC-USDT","ETH":"ETH-USDT","SOL":"SOL-USDT","BNB":"BNB-USDT","XRP":"XRP-USDT","ADA":"ADA-USDT","AVAX":"AVAX-USDT","DOT":"DOT-USDT","LINK":"LINK-USDT","MATIC":"MATIC-USDT"}
        self.timeframe_mapping = {"1m":"1m","5m":"5m","15m":"15m","30m":"30m","1h":"1h","4h":"4h","1d":"1d","1w":"1w","1mo":"1w"}

        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504]
            )
        ))
        self.session.verify = True

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        if self.api_version == "v5":
            url = f"{self.base_url}/api/v5/{endpoint}"
        else:
            url = f"{self.base_url}{endpoint}"
        params = params or {}

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "QuantAgent-v2/1.0"
        }

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()

                if self.api_version == "v5":
                    if isinstance(data, dict) and is_v5_success(data):
                        return data
                    elif isinstance(data, list):
                        return {"status": "success", "data": data}
                    else:
                        if isinstance(data, dict):
                            logger.warning(f"V5 API returned error: code={data.get('code')}, msg={data.get('msg')}")
                        return data
                else:
                    # v1 logic
                    if data.get("status") == "success":
                        return data
                    elif "exchanges" in data or "data" in data or isinstance(data, list):
                        return {"status": "success", "data": data}
                    else:
                        logger.warning(f"API returned error: {data}")

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {str(e)}")
                if attempt < self.max_retries:
                    time.sleep(1)
                else:
                    raise

        raise Exception("API request failed after retries")

    def check_health(self) -> Dict[str, Any]:
        try:
            start_time = time.time()
            if self.api_version == "v5":
                self._make_request("public/instruments", {"instType": "SPOT", "instId": "BTC-USDT"})
            else:
                self._make_request("/api/v1/healthz")
            return {
                "status": "healthy",
                "response_time": time.time() - start_time
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    def _convert_symbol(self, symbol: str) -> str:
        if self.api_version == "v5":
            return convert_symbol_for_v5(symbol, self.okx_inst_type)

        symbol = (symbol or "").strip()
        if not symbol:
            return symbol

        if "/" in symbol:
            base, quote = symbol.split("/", 1)
            symbol = f"{base}-{quote}"

        symbol = symbol.upper()

        if symbol in self.symbol_mapping:
            return self.symbol_mapping[symbol]

        if "-" in symbol:
            return symbol

        if symbol.endswith("USDT") and len(symbol) > 4:
            base = symbol[:-4]
            return f"{base}-USDT"

        return f"{symbol}-USDT"

    def _convert_timeframe(self, timeframe: str) -> str:
        if self.api_version == "v5":
            return convert_timeframe_v1_to_v5(timeframe)
        return self.timeframe_mapping.get(timeframe, "1h")

    @staticmethod
    def _date_str_to_unix_ms(date_str: str) -> int | None:
        """Convert date string like '2025-01-01' or '2025-01-01 12:00:00' to Unix ms."""
        try:
            return int(pd.Timestamp(date_str).value // 1_000_000)
        except Exception:
            return None

    def get_ohlcv_data(self, symbol: str, timeframe: str = "1h",
                      limit: int = 100, exchange: str = "okx",
                      start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        try:
            if self.api_version == "v5":
                # --- v5 path ---
                api_symbol = self._convert_symbol(symbol)
                api_timeframe = self._convert_timeframe(timeframe)

                params = build_v5_ohlcv_params(
                    instId=api_symbol,
                    bar=api_timeframe,
                    limit=min(limit, 300),
                )

                if start_date:
                    before_ts = self._date_str_to_unix_ms(start_date)
                    if before_ts is not None:
                        params["before"] = str(before_ts)  # OKX: before = return data AFTER this timestamp
                if end_date:
                    after_ts = self._date_str_to_unix_ms(end_date)
                    if after_ts is not None:
                        params["after"] = str(after_ts)  # OKX: after = return data BEFORE this timestamp

                # 历史查询走 history-candles（不受 500 条缓存限制），实时查询走 candles
                endpoint = "market/history-candles" if (start_date or end_date) else "market/candles"
                data = self._make_request(endpoint, params)
                return parse_v5_ohlcv_to_dataframe(data)

            # --- v1 path (backward compat) ---
            api_symbol = self._convert_symbol(symbol)
            api_timeframe = self._convert_timeframe(timeframe)

            params = {
                "symbol": api_symbol,
                "timeframe": api_timeframe,
                "limit": min(limit, 1000),
                "exchange": exchange
            }

            if start_date:
                params["start_time"] = start_date
            if end_date:
                params["end_time"] = end_date

            data = self._make_request("/api/v1/ohlcv", params)

            if not data.get("data"):
                return None

            ohlcv_data = data["data"]
            if not ohlcv_data:
                return None

            df = pd.DataFrame(ohlcv_data)
            if df.empty or len(df.columns) == 0:
                return None

            column_mapping = {
                "timestamp": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume"
            }

            if df.columns is not None and len(df.columns) > 0:
                df.columns = [column_mapping.get(col.lower(), col) for col in df.columns]
            else:
                return None

            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'])
                df.set_index('Date', inplace=True)

            numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.sort_index()
            return df

        except Exception as e:
            logger.error(f"Failed to get OHLCV data: {str(e)}")
            return None

    def get_ohlcv_data_enhanced(self, symbol: str, timeframe: str = "1h",
                               limit: int = 100, exchange: str = "okx",
                               method: str = "latest", start_date: str = None,
                               end_date: str = None) -> Optional[pd.DataFrame]:
        if method == "date_range" and (not start_date or not end_date):
            raise ValueError("date_range method requires start_date and end_date")
        elif method == "to_end" and not end_date:
            raise ValueError("to_end method requires end_date")

        if method == "to_end":
            return self.get_ohlcv_data(symbol, timeframe, limit, exchange, None, end_date)
        elif method == "date_range":
            return self.get_ohlcv_data(symbol, timeframe, limit, exchange, start_date, end_date)
        else:
            return self.get_ohlcv_data(symbol, timeframe, limit, exchange, None, None)

    def get_latest_price(self, symbol: str, exchange: str = "okx") -> Optional[float]:
        df = self.get_ohlcv_data(symbol, "1h", 1, exchange)
        if df is not None and len(df) > 0:
            return float(df['Close'].iloc[-1])
        return None

    def get_websocket_url(self, symbols: List[str], exchange: str = "okx") -> str:
        converted_symbols = [self._convert_symbol(s) for s in symbols]
        symbols_str = ",".join(converted_symbols)
        return f"{self.base_url.replace('http', 'ws')}/ws/realtime?exchange={exchange}&symbols={symbols_str}"

    def get_exchanges(self) -> List[str]:
        if self.api_version == "v5":
            return ["okx"]
        try:
            data = self._make_request("/api/v1/exchanges")
            return data.get("data", [])
        except Exception:
            return ["okx"]

    # ========================================================================
    # Derivative Data Methods (brale-core migration)
    # ========================================================================

    def _extract_ccy(self, symbol: str) -> str:
        """Extract currency from symbol: 'BTC-USDT-SWAP' → 'BTC'."""
        symbol = (symbol or "").strip().upper()
        if not symbol:
            return ""
        parts = symbol.replace("/", "-").split("-")
        if len(parts) >= 1:
            return parts[0]
        return symbol

    def fetch_open_interest(self, symbol: str) -> dict | None:
        """GET /api/v5/public/open-interest — snapshot, current value only."""
        try:
            api_symbol = self._convert_symbol(symbol)
            data = self._make_request("public/open-interest", {"instId": api_symbol})
            if is_v5_success(data):
                raw = get_v5_data(data)
                if raw and isinstance(raw, list) and len(raw) > 0:
                    item = raw[0]
                    return {
                        "instId": item.get("instId", api_symbol),
                        "oi": float(item.get("oi", 0)),
                        "oiCcy": float(item.get("oiCcy", 0)),
                        "ts": item.get("ts", ""),
                    }
            logger.warning(f"fetch_open_interest returned empty: {symbol}")
            return None
        except Exception as e:
            logger.error(f"fetch_open_interest failed for {symbol}: {e}")
            return None

    def fetch_open_interest_history(self, symbol: str, period: str = "1H", limit: int = 24) -> list[dict] | None:
        """GET /api/v5/rubik/stat/contracts/open-interest-volume — history, **after无效**."""
        try:
            ccy = self._extract_ccy(symbol)
            data = self._make_request("rubik/stat/contracts/open-interest-volume", {
                "ccy": ccy,
                "period": period,
                "limit": min(limit, 100),
            })
            if is_v5_success(data):
                raw = get_v5_data(data)
                if raw and isinstance(raw, list):
                    return [
                        {
                            "ts": r.get("ts", ""),
                            "oi": float(r.get("oi", 0)),
                            "vol": float(r.get("vol", 0)),
                        }
                        for r in raw
                    ]
            logger.warning(f"fetch_open_interest_history returned empty: {symbol}")
            return None
        except Exception as e:
            logger.error(f"fetch_open_interest_history failed for {symbol}: {e}")
            return None

    def fetch_funding_rate_history(self, symbol: str, limit: int = 24, after: int | None = None) -> list[dict] | None:
        """GET /api/v5/public/funding-rate-history — supports 'after' pagination."""
        try:
            api_symbol = self._convert_symbol(symbol)
            params: dict = {"instId": api_symbol, "limit": str(min(limit, 100))}
            if after is not None:
                params["after"] = str(after)
            data = self._make_request("public/funding-rate-history", params)
            if is_v5_success(data):
                raw = get_v5_data(data)
                if raw and isinstance(raw, list):
                    return [
                        {
                            "instId": r.get("instId", api_symbol),
                            "fundingTime": r.get("fundingTime", ""),
                            "fundingRate": float(r.get("fundingRate", 0)),
                            "realizedRate": float(r.get("realizedRate", 0)),
                            "nextFundingTime": r.get("nextFundingTime", ""),
                            "ts": r.get("ts", ""),
                        }
                        for r in raw
                    ]
            logger.warning(f"fetch_funding_rate_history returned empty: {symbol}")
            return None
        except Exception as e:
            logger.error(f"fetch_funding_rate_history failed for {symbol}: {e}")
            return None

    def fetch_long_short_ratio(self, symbol: str, period: str = "1H", limit: int = 24) -> list[dict] | None:
        """GET /api/v5/rubik/stat/contracts/long-short-account-ratio — **after无效**."""
        try:
            ccy = self._extract_ccy(symbol)
            data = self._make_request("rubik/stat/contracts/long-short-account-ratio", {
                "ccy": ccy,
                "period": period,
                "limit": min(limit, 100),
            })
            if is_v5_success(data):
                raw = get_v5_data(data)
                if raw and isinstance(raw, list):
                    return [
                        {
                            "ts": r.get("ts", ""),
                            "longRatio": float(r.get("longRatio", 0)),
                            "shortRatio": float(r.get("shortRatio", 0)),
                            "longShortRatio": float(r.get("longShortRatio", 0)),
                        }
                        for r in raw
                    ]
            logger.warning(f"fetch_long_short_ratio returned empty: {symbol}")
            return None
        except Exception as e:
            logger.error(f"fetch_long_short_ratio failed for {symbol}: {e}")
            return None

    def fetch_taker_volume_ratio(self, symbol: str, period: str = "1H", limit: int = 24) -> list[dict] | None:
        """GET /api/v5/rubik/stat/contracts/taker-volume-ratio — **after无效**."""
        try:
            ccy = self._extract_ccy(symbol)
            data = self._make_request("rubik/stat/contracts/taker-volume-ratio", {
                "ccy": ccy,
                "period": period,
                "limit": min(limit, 100),
            })
            if is_v5_success(data):
                raw = get_v5_data(data)
                if raw and isinstance(raw, list):
                    return [
                        {
                            "ts": r.get("ts", ""),
                            "buyVol": float(r.get("buyVol", 0)),
                            "sellVol": float(r.get("sellVol", 0)),
                            "buyRatio": float(r.get("buyRatio", 0)),
                            "sellRatio": float(r.get("sellRatio", 0)),
                        }
                        for r in raw
                    ]
            logger.warning(f"fetch_taker_volume_ratio returned empty: {symbol}")
            return None
        except Exception as e:
            logger.error(f"fetch_taker_volume_ratio failed for {symbol}: {e}")
            return None

    def fetch_liquidation_orders(self, symbol: str, limit: int = 16) -> list[dict] | None:
        """GET /api/v5/public/liquidation-orders — uly param, ~16 entries max."""
        try:
            ccy = self._extract_ccy(symbol)
            data = self._make_request("public/liquidation-orders", {
                "uly": f"{ccy}-USDT",
                "limit": min(limit, 20),
                "state": "filled",
            })
            if is_v5_success(data):
                raw = get_v5_data(data)
                if raw and isinstance(raw, list):
                    return [
                        {
                            "instId": r.get("instId", ""),
                            "uly": r.get("uly", ""),
                            "side": r.get("side", ""),
                            "posSide": r.get("posSide", ""),
                            "sz": float(r.get("sz", 0)),
                            "bkPx": float(r.get("bkPx", 0)),
                            "bkLoss": float(r.get("bkLoss", 0)),
                            "ts": r.get("ts", ""),
                        }
                        for r in raw
                    ]
            logger.warning(f"fetch_liquidation_orders returned empty: {symbol}")
            return None
        except Exception as e:
            logger.error(f"fetch_liquidation_orders failed for {symbol}: {e}")
            return None
