import requests
import logging
import time
import json
import pandas as pd
from typing import Dict, Optional, Any, List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.core.config import settings

logger = logging.getLogger(__name__)

class MarketDataService:
    """
    Service for fetching market data from the Quant API.
    Refactored from core/quant_api_client.py
    """

    def __init__(self):
        self.base_url = settings.MARKET_DATA_API_URL.rstrip('/')
        self.api_token = settings.MARKET_DATA_API_TOKEN.get_secret_value()
        self.timeout = 15
        self.max_retries = 2
        
        self.session = requests.Session()
        self.session.mount('https://', HTTPAdapter(
            max_retries=Retry(
                total=3,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504]
            )
        ))
        self.session.verify = True

        # Symbol mapping
        self.symbol_mapping = {
            "BTC": "BTC-USDT",
            "ETH": "ETH-USDT",
            "SOL": "SOL-USDT",
            "BNB": "BNB-USDT",
            "XRP": "XRP-USDT",
            "ADA": "ADA-USDT",
            "AVAX": "AVAX-USDT",
            "DOT": "DOT-USDT",
            "LINK": "LINK-USDT",
            "MATIC": "MATIC-USDT"
        }

        # Timeframe mapping
        self.timeframe_mapping = {
            "1m": "1m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "4h",
            "1d": "1d",
            "1w": "1w",
            "1mo": "1w"
        }

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
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
        if symbol in self.symbol_mapping:
            return self.symbol_mapping[symbol]
        
        if '-' in symbol and 'USD' in symbol:
            return symbol
        elif symbol in ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA']:
            return f"{symbol}-USDT"
        else:
            return f"{symbol}-USDT"

    def _convert_timeframe(self, timeframe: str) -> str:
        return self.timeframe_mapping.get(timeframe, "1h")

    def get_ohlcv_data(self, symbol: str, timeframe: str = "1h",
                      limit: int = 100, exchange: str = "okx",
                      start_date: str = None, end_date: str = None) -> Optional[pd.DataFrame]:
        try:
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
        try:
            data = self._make_request("/api/v1/exchanges")
            return data.get("data", [])
        except Exception:
            return ["okx"]
