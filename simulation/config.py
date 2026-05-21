"""
仿真模拟交易模块 - 全局配置
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── 现有后端分析 API ──
    ANALYZE_API_URL: str = "http://localhost:8000/api/v1/analyze/"
    ANALYZE_TIMEOUT: int = 120
    ANALYZE_RETRY_COUNT: int = 2
    ANALYZE_RETRY_DELAY: int = 10

    # ── 行情数据（OKX v5 透传代理）──
    MARKET_DATA_API_URL: str = "https://webui.caomaowu.lol"
    MARKET_DATA_API_TOKEN: str = ""

    # ── 模拟模块自身服务 ──
    SIM_HOST: str = "0.0.0.0"
    SIM_PORT: int = 18520

    # ── 数据库 ──
    DB_PATH: str = str(Path(__file__).parent / "data" / "simulation.db")

    # ── K线调度 ──
    KLINE_BUFFER_SECONDS: int = 0

    # ── 预分析提前量（K线收盘前多少秒启动预分析）──
    # 策略：短周期提前50s、长周期提前70s，确保分析完成时有足够入场时间
    PRE_ANALYZE_OFFSETS: dict[str, int] = {
        "5m": 50,
        "15m": 50,
        "1h": 70,
        "4h": 70,
        "1d": 70,
    }

    # ── 默认参数 ──
    DEFAULT_INITIAL_CAPITAL: float = 10000.0
    DEFAULT_BET_AMOUNT: float = 100.0
    DEFAULT_FEE_RATE: float = 0.0
    DEFAULT_KLINE_COUNT: int = 100

    # ── WebSocket ──
    WS_HEARTBEAT_INTERVAL: int = 30


settings = Settings()
