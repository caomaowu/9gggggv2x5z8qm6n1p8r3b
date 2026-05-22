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
    KLINE_BUFFER_SECONDS: int = 4

    # ── 预分析提前量（K线收盘前多少秒启动预分析），可按周期在 .env 单独覆盖 ──
    PRE_ANALYZE_OFFSET_5M: int = 70
    PRE_ANALYZE_OFFSET_15M: int = 70
    PRE_ANALYZE_OFFSET_1H: int = 70
    PRE_ANALYZE_OFFSET_4H: int = 70
    PRE_ANALYZE_OFFSET_1D: int = 70

    @property
    def pre_analyze_offsets(self) -> dict[str, int]:
        return {
            "5m": self.PRE_ANALYZE_OFFSET_5M,
            "15m": self.PRE_ANALYZE_OFFSET_15M,
            "1h": self.PRE_ANALYZE_OFFSET_1H,
            "4h": self.PRE_ANALYZE_OFFSET_4H,
            "1d": self.PRE_ANALYZE_OFFSET_1D,
        }

    # ── 默认参数 ──
    DEFAULT_INITIAL_CAPITAL: float = 10000.0
    DEFAULT_BET_AMOUNT: float = 100.0
    DEFAULT_FEE_RATE: float = 0.0
    DEFAULT_KLINE_COUNT: int = 100
    DEFAULT_MODEL_PROVIDER: str = ""
    DEFAULT_MODEL_NAME: str = ""

    # ── WebSocket ──
    WS_HEARTBEAT_INTERVAL: int = 30


settings = Settings()
