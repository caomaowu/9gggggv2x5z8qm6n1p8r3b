"""Pydantic v2 models for the simulation API layer.

All datetime fields are ISO 8601 strings (not datetime objects).
Response models use from_attributes=True to work with dict data.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ── Enums ────────────────────────────────────────────────────────────────


class TaskStatus(StrEnum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"


class BetMode(StrEnum):
    FIXED = "fixed"
    PERCENT = "percent"


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


class RoundResult(StrEnum):
    WIN = "WIN"
    LOSE = "LOSE"
    SKIP = "SKIP"


class RoundStatus(StrEnum):
    BET_PLACED = "BET_PLACED"
    SETTLED = "SETTLED"


class WsMessageType(StrEnum):
    TASK_STARTED = "task_started"
    TASK_STOPPED = "task_stopped"
    TASK_DELETED = "task_deleted"
    TASK_UPDATED = "task_updated"
    ROUND_COMPLETED = "round_completed"
    STATS_UPDATED = "stats_updated"


# ── Request models ───────────────────────────────────────────────────────


class TaskCreateRequest(BaseModel):
    """Request body for creating a new simulation task."""

    asset: str = Field(..., min_length=1, max_length=20, description="交易对, e.g. BTC-USDT")
    timeframe: str = Field(..., min_length=1, description="K线周期, e.g. 15m, 1h, 4h, 1d")
    bet_mode: BetMode = Field(default=BetMode.FIXED, description="押注模式")
    bet_amount: float = Field(default=100.0, gt=0, description="固定押注金额(USDT)")
    bet_percent: float | None = Field(default=None, gt=0, le=1.0, description="百分比押注比例")
    fee_rate: float = Field(default=0.0, ge=0, lt=1.0, description="手续费率")
    initial_capital: float = Field(default=10000.0, gt=0, description="初始资金")

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, v: str) -> str:
        """Ensure timeframe is non-empty after stripping whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("timeframe must not be empty")
        return stripped

    @field_validator("bet_percent")
    @classmethod
    def validate_bet_percent(cls, v: float | None, info) -> float | None:
        """When bet_mode is PERCENT, bet_percent is required."""
        if v is None:
            return None
        return v


class TaskUpdateRequest(BaseModel):
    """Request body for updating an existing task's parameters."""

    bet_amount: float | None = Field(default=None, gt=0)
    bet_mode: BetMode | None = Field(default=None)
    bet_percent: float | None = Field(default=None, gt=0, le=1.0)
    fee_rate: float | None = Field(default=None, ge=0, lt=1.0)


# ── Response models ──────────────────────────────────────────────────────


class TaskResponse(BaseModel):
    """Full task representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    asset: str
    timeframe: str
    status: TaskStatus
    bet_amount: float
    bet_mode: BetMode
    bet_percent: float | None = None
    fee_rate: float
    initial_capital: float
    current_capital: float
    total_rounds: int
    wins: int
    losses: int
    skips: int
    best_win_streak: int
    worst_lose_streak: int
    current_streak: str | None = None
    last_kline_ts: str | None = None
    created_at: str
    updated_at: str


class RoundResponse(BaseModel):
    """Full round representation returned by the API.

    All optional fields are properly typed as Optional[...] to handle
    NULL values from the database (e.g. unsettled rounds).
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    round_seq: int
    status: RoundStatus
    trigger_kline_ts: str
    trigger_kline_open: float | None = None
    trigger_kline_close: float | None = None
    direction: str | None = None
    score: float | None = None
    confidence: float | None = None
    entry_point: float | None = None
    indicator_score: float | None = None
    indicator_confidence: float | None = None
    structure_score: float | None = None
    structure_confidence: float | None = None
    mechanics_score: float | None = None
    mechanics_confidence: float | None = None
    indicator_summary: str | None = None
    structure_summary: str | None = None
    mechanics_summary: str | None = None
    fusion_raw: str | None = None
    bet_direction: str | None = None
    bet_amount: float | None = None
    fee_amount: float = 0.0
    settle_kline_ts: str | None = None
    settle_price: float | None = None
    result: RoundResult | None = None
    pnl: float | None = None
    created_at: str
    settled_at: str | None = None


class EquityPoint(BaseModel):
    """A single point on the equity curve."""

    round_seq: int
    pnl: float
    cumulative_pnl: float


class StatsResponse(BaseModel):
    """Aggregated statistics for a task."""

    model_config = ConfigDict(from_attributes=True)

    task_id: str
    total_rounds: int
    wins: int
    losses: int
    skips: int
    win_rate: float
    total_pnl: float
    current_capital: float
    roi: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    best_win_streak: int
    worst_lose_streak: int
    current_streak: str | None = None


class RoundListResponse(BaseModel):
    """Paginated list of rounds."""

    rounds: list[RoundResponse]
    total: int
    offset: int
    limit: int


# ── WebSocket message models ─────────────────────────────────────────────


class WsMessage(BaseModel):
    """Message envelope for WebSocket communication."""

    type: WsMessageType
    task_id: str
    data: dict = {}
