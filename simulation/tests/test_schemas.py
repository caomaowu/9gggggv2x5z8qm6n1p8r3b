"""Tests for simulation Pydantic schemas."""

import json
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from simulation.models.schemas import (
    BetMode,
    Direction,
    EquityPoint,
    RoundListResponse,
    RoundResponse,
    RoundResult,
    RoundStatus,
    StatsResponse,
    TaskCreateRequest,
    TaskResponse,
    TaskStatus,
    TaskUpdateRequest,
    WsMessage,
    WsMessageType,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def valid_task_create_data() -> Dict[str, Any]:
    return {
        "asset": "BTC-USDT",
        "timeframe": "15m",
        "bet_mode": "fixed",
        "bet_amount": 100.0,
        "fee_rate": 0.001,
        "initial_capital": 10000.0,
    }


def valid_task_response_data() -> Dict[str, Any]:
    return {
        "id": "task_001",
        "asset": "BTC-USDT",
        "timeframe": "15m",
        "status": "RUNNING",
        "bet_amount": 100.0,
        "bet_mode": "fixed",
        "bet_percent": None,
        "fee_rate": 0.001,
        "initial_capital": 10000.0,
        "current_capital": 10500.0,
        "total_rounds": 10,
        "wins": 6,
        "losses": 3,
        "skips": 1,
        "best_win_streak": 4,
        "worst_lose_streak": 2,
        "current_streak": "2W",
        "last_kline_ts": "2025-05-19T10:30:00Z",
        "created_at": "2025-05-18T08:00:00Z",
        "updated_at": "2025-05-19T10:30:00Z",
    }


# ── Enum tests ───────────────────────────────────────────────────────────


class TestEnums:
    def test_task_status_values(self):
        assert TaskStatus.STOPPED.value == "STOPPED"
        assert TaskStatus.RUNNING.value == "RUNNING"

    def test_bet_mode_values(self):
        assert BetMode.FIXED.value == "fixed"
        assert BetMode.PERCENT.value == "percent"

    def test_direction_values(self):
        assert Direction.LONG.value == "long"
        assert Direction.SHORT.value == "short"
        assert Direction.NONE.value == "none"

    def test_round_result_values(self):
        assert RoundResult.WIN.value == "WIN"
        assert RoundResult.LOSE.value == "LOSE"
        assert RoundResult.SKIP.value == "SKIP"

    def test_round_status_values(self):
        assert RoundStatus.BET_PLACED.value == "BET_PLACED"
        assert RoundStatus.SETTLED.value == "SETTLED"

    def test_ws_message_type_values(self):
        assert WsMessageType.TASK_STARTED.value == "task_started"
        assert WsMessageType.TASK_STOPPED.value == "task_stopped"
        assert WsMessageType.TASK_DELETED.value == "task_deleted"
        assert WsMessageType.ROUND_COMPLETED.value == "round_completed"
        assert WsMessageType.STATS_UPDATED.value == "stats_updated"

    def test_invalid_enum_value_raises(self):
        with pytest.raises(ValueError):
            TaskStatus("INVALID")

    def test_enum_from_valid_string(self):
        assert TaskStatus("RUNNING") == TaskStatus.RUNNING


# ── TaskCreateRequest tests ──────────────────────────────────────────────


class TestTaskCreateRequest:
    def test_valid_minimal(self):
        """Should succeed with only required fields (others use defaults)."""
        data = {"asset": "ETH-USDT", "timeframe": "1h"}
        model = TaskCreateRequest(**data)
        assert model.asset == "ETH-USDT"
        assert model.timeframe == "1h"
        assert model.bet_mode == BetMode.FIXED
        assert model.bet_amount == 100.0
        assert model.bet_percent is None
        assert model.fee_rate == 0.0
        assert model.initial_capital == 10000.0

    def test_valid_full(self):
        """Should succeed with all fields provided."""
        data = valid_task_create_data()
        model = TaskCreateRequest(**data)
        assert model.asset == "BTC-USDT"
        assert model.timeframe == "15m"
        assert model.bet_mode == BetMode.FIXED
        assert model.bet_amount == 100.0
        assert model.fee_rate == 0.001
        assert model.initial_capital == 10000.0

    def test_valid_percent_mode(self):
        """Percent mode with bet_percent in (0,1] should work."""
        data = valid_task_create_data()
        data["bet_mode"] = "percent"
        data["bet_percent"] = 0.5
        model = TaskCreateRequest(**data)
        assert model.bet_mode == BetMode.PERCENT
        assert model.bet_percent == 0.5

    def test_missing_asset_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(timeframe="15m")

    def test_missing_timeframe_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(asset="BTC-USDT")

    def test_empty_asset_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(asset="", timeframe="15m")

    def test_asset_too_long_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(asset="X" * 21, timeframe="15m")

    def test_negative_bet_amount_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(asset="BTC-USDT", timeframe="15m", bet_amount=-10)

    def test_zero_bet_amount_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(asset="BTC-USDT", timeframe="15m", bet_amount=0)

    def test_bet_percent_too_high_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(
                asset="BTC-USDT",
                timeframe="15m",
                bet_mode="percent",
                bet_percent=1.5,
            )

    def test_bet_percent_zero_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(
                asset="BTC-USDT",
                timeframe="15m",
                bet_mode="percent",
                bet_percent=0,
            )

    def test_fee_rate_negative_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(asset="BTC-USDT", timeframe="15m", fee_rate=-0.01)

    def test_fee_rate_equal_one_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(asset="BTC-USDT", timeframe="15m", fee_rate=1.0)

    def test_initial_capital_zero_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(asset="BTC-USDT", timeframe="15m", initial_capital=0)

    def test_initial_capital_negative_raises(self):
        with pytest.raises(ValidationError):
            TaskCreateRequest(asset="BTC-USDT", timeframe="15m", initial_capital=-100)

    def test_enum_coercion(self):
        """String values should be accepted and coerced to Enum."""
        data = valid_task_create_data()
        data["bet_mode"] = "percent"
        model = TaskCreateRequest(**data)
        assert isinstance(model.bet_mode, BetMode)
        assert model.bet_mode == BetMode.PERCENT


# ── TaskUpdateRequest tests ──────────────────────────────────────────────


class TestTaskUpdateRequest:
    def test_all_fields_none(self):
        """All fields optional — empty body should be valid."""
        model = TaskUpdateRequest()
        assert model.bet_amount is None
        assert model.bet_percent is None
        assert model.fee_rate is None

    def test_single_field_update(self):
        model = TaskUpdateRequest(bet_amount=200.0)
        assert model.bet_amount == 200.0
        assert model.bet_percent is None
        assert model.fee_rate is None

    def test_invalid_bet_amount_raises(self):
        with pytest.raises(ValidationError):
            TaskUpdateRequest(bet_amount=0)

    def test_invalid_bet_percent_raises(self):
        with pytest.raises(ValidationError):
            TaskUpdateRequest(bet_percent=0)

    def test_invalid_fee_rate_raises(self):
        with pytest.raises(ValidationError):
            TaskUpdateRequest(fee_rate=1.0)


# ── TaskResponse tests ───────────────────────────────────────────────────


class TestTaskResponse:
    def test_from_dict(self):
        data = valid_task_response_data()
        model = TaskResponse(**data)
        assert model.id == "task_001"
        assert model.status == TaskStatus.RUNNING
        assert model.current_capital == 10500.0
        assert model.total_rounds == 10

    def test_enum_coercion(self):
        data = valid_task_response_data()
        data["status"] = "STOPPED"
        model = TaskResponse(**data)
        assert isinstance(model.status, TaskStatus)
        assert model.status == TaskStatus.STOPPED

    def test_bet_mode_coercion(self):
        data = valid_task_response_data()
        data["bet_mode"] = "percent"
        data["bet_percent"] = 0.5
        model = TaskResponse(**data)
        assert isinstance(model.bet_mode, BetMode)
        assert model.bet_mode == BetMode.PERCENT

    def test_current_streak_none(self):
        data = valid_task_response_data()
        data["current_streak"] = None
        model = TaskResponse(**data)
        assert model.current_streak is None

    def test_last_kline_ts_none(self):
        data = valid_task_response_data()
        data["last_kline_ts"] = None
        model = TaskResponse(**data)
        assert model.last_kline_ts is None

    def test_serialize_to_dict(self):
        data = valid_task_response_data()
        model = TaskResponse(**data)
        d = model.model_dump()
        assert d["id"] == "task_001"
        assert d["status"] == "RUNNING"
        assert d["bet_mode"] == "fixed"


# ── RoundResponse tests ──────────────────────────────────────────────────


class TestRoundResponse:
    def test_settled_round(self):
        """A fully settled round with all fields populated."""
        data = {
            "id": "round_001",
            "task_id": "task_001",
            "round_seq": 1,
            "status": "SETTLED",
            "trigger_kline_ts": "2025-05-19T10:00:00Z",
            "trigger_kline_open": 50000.0,
            "trigger_kline_close": 50100.0,
            "direction": "long",
            "score": 85.0,
            "confidence": 0.75,
            "entry_point": 50050.0,
            "indicator_score": 80.0,
            "indicator_confidence": 0.7,
            "structure_score": 90.0,
            "structure_confidence": 0.8,
            "mechanics_score": 85.0,
            "mechanics_confidence": 0.75,
            "indicator_summary": "RSI bullish",
            "structure_summary": "Support level",
            "mechanics_summary": "Volume spike",
            "fusion_raw": '{"signal": "buy", "strength": 0.8}',
            "bet_direction": "long",
            "bet_amount": 100.0,
            "fee_amount": 0.1,
            "settle_kline_ts": "2025-05-19T10:30:00Z",
            "settle_price": 50200.0,
            "result": "WIN",
            "pnl": 150.0,
            "created_at": "2025-05-19T10:00:00Z",
            "settled_at": "2025-05-19T10:30:00Z",
        }
        model = RoundResponse(**data)
        assert model.id == "round_001"
        assert model.status == RoundStatus.SETTLED
        assert model.result == RoundResult.WIN
        assert model.pnl == 150.0
        assert model.settle_price == 50200.0

    def test_unsettled_round(self):
        """An unsettled round (BET_PLACED) with many None fields."""
        data = {
            "id": "round_002",
            "task_id": "task_001",
            "round_seq": 2,
            "status": "BET_PLACED",
            "trigger_kline_ts": "2025-05-19T11:00:00Z",
            "trigger_kline_open": None,
            "trigger_kline_close": None,
            "direction": None,
            "score": None,
            "confidence": None,
            "entry_point": None,
            "indicator_score": None,
            "indicator_confidence": None,
            "structure_score": None,
            "structure_confidence": None,
            "mechanics_score": None,
            "mechanics_confidence": None,
            "indicator_summary": None,
            "structure_summary": None,
            "mechanics_summary": None,
            "fusion_raw": None,
            "bet_direction": None,
            "bet_amount": None,
            "fee_amount": 0.0,
            "settle_kline_ts": None,
            "settle_price": None,
            "result": None,
            "pnl": None,
            "created_at": "2025-05-19T11:00:00Z",
            "settled_at": None,
        }
        model = RoundResponse(**data)
        assert model.id == "round_002"
        assert model.status == RoundStatus.BET_PLACED
        assert model.result is None
        assert model.pnl is None
        assert model.settle_price is None
        assert model.settled_at is None
        assert model.score is None
        assert model.entry_point is None

    def test_partial_data_defaults(self):
        """Round with only required fields; optionals get defaults."""
        data = {
            "id": "round_003",
            "task_id": "task_001",
            "round_seq": 3,
            "status": "BET_PLACED",
            "trigger_kline_ts": "2025-05-19T12:00:00Z",
            "fee_amount": 0.0,
            "created_at": "2025-05-19T12:00:00Z",
        }
        model = RoundResponse(**data)
        assert model.fee_amount == 0.0
        assert model.trigger_kline_open is None
        assert model.direction is None
        assert model.result is None

    def test_enum_coercion(self):
        data = {
            "id": "round_004",
            "task_id": "task_001",
            "round_seq": 4,
            "status": "SETTLED",
            "trigger_kline_ts": "2025-05-19T13:00:00Z",
            "fee_amount": 0.0,
            "result": "LOSE",
            "created_at": "2025-05-19T13:00:00Z",
        }
        model = RoundResponse(**data)
        assert isinstance(model.status, RoundStatus)
        assert isinstance(model.result, RoundResult)
        assert model.result == RoundResult.LOSE


# ── EquityPoint tests ────────────────────────────────────────────────────


class TestEquityPoint:
    def test_valid(self):
        ep = EquityPoint(round_seq=1, pnl=100.0, cumulative_pnl=500.0)
        assert ep.round_seq == 1
        assert ep.pnl == 100.0
        assert ep.cumulative_pnl == 500.0

    def test_negative_pnl(self):
        ep = EquityPoint(round_seq=2, pnl=-50.0, cumulative_pnl=450.0)
        assert ep.pnl == -50.0


# ── StatsResponse tests ──────────────────────────────────────────────────


class TestStatsResponse:
    def test_from_dict(self):
        data = {
            "task_id": "task_001",
            "total_rounds": 20,
            "wins": 12,
            "losses": 6,
            "skips": 2,
            "win_rate": 0.6,
            "total_pnl": 500.0,
            "current_capital": 10500.0,
            "roi": 0.05,
            "max_drawdown": 0.1,
            "sharpe_ratio": 1.5,
            "profit_factor": 2.0,
            "best_win_streak": 5,
            "worst_lose_streak": 3,
            "current_streak": "3W",
        }
        model = StatsResponse(**data)
        assert model.task_id == "task_001"
        assert model.win_rate == 0.6
        assert model.sharpe_ratio == 1.5
        assert model.profit_factor == 2.0
        assert model.current_streak == "3W"

    def test_no_streak(self):
        data = {
            "task_id": "task_001",
            "total_rounds": 0,
            "wins": 0,
            "losses": 0,
            "skips": 0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "current_capital": 10000.0,
            "roi": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "profit_factor": 0.0,
            "best_win_streak": 0,
            "worst_lose_streak": 0,
            "current_streak": None,
        }
        model = StatsResponse(**data)
        assert model.current_streak is None

    def test_serialize_to_json(self):
        data = {
            "task_id": "task_001",
            "total_rounds": 20,
            "wins": 12,
            "losses": 6,
            "skips": 2,
            "win_rate": 0.6,
            "total_pnl": 500.0,
            "current_capital": 10500.0,
            "roi": 0.05,
            "max_drawdown": 0.1,
            "sharpe_ratio": 1.5,
            "profit_factor": 2.0,
            "best_win_streak": 5,
            "worst_lose_streak": 3,
            "current_streak": "3W",
        }
        model = StatsResponse(**data)
        dumped = model.model_dump()
        # Verify JSON-serializable
        json_str = json.dumps(dumped)
        restored = json.loads(json_str)
        assert restored["task_id"] == "task_001"
        assert restored["win_rate"] == 0.6


# ── RoundListResponse tests ──────────────────────────────────────────────


class TestRoundListResponse:
    def test_empty_list(self):
        model = RoundListResponse(rounds=[], total=0, offset=0, limit=20)
        assert model.rounds == []
        assert model.total == 0

    def test_with_rounds(self):
        round_data = {
            "id": "round_001",
            "task_id": "task_001",
            "round_seq": 1,
            "status": "SETTLED",
            "trigger_kline_ts": "2025-05-19T10:00:00Z",
            "fee_amount": 0.0,
            "result": "WIN",
            "pnl": 100.0,
            "created_at": "2025-05-19T10:00:00Z",
        }
        model = RoundListResponse(rounds=[RoundResponse(**round_data)], total=1, offset=0, limit=20)
        assert len(model.rounds) == 1
        assert model.rounds[0].id == "round_001"
        assert model.total == 1


# ── WsMessage tests ──────────────────────────────────────────────────────


class TestWsMessage:
    def test_minimal(self):
        msg = WsMessage(type="task_started", task_id="task_001")
        assert msg.type == WsMessageType.TASK_STARTED
        assert msg.task_id == "task_001"
        assert msg.data == {}

    def test_with_data(self):
        msg = WsMessage(
            type="round_completed",
            task_id="task_001",
            data={"round_id": "round_001", "pnl": 150.0},
        )
        assert msg.type == WsMessageType.ROUND_COMPLETED
        assert msg.data["pnl"] == 150.0

    def test_serialize_to_json(self):
        msg = WsMessage(type="stats_updated", task_id="task_001", data={"total_rounds": 10})
        dumped = msg.model_dump()
        json_str = json.dumps(dumped)
        restored = json.loads(json_str)
        assert restored["type"] == "stats_updated"
        assert restored["task_id"] == "task_001"
        assert restored["data"]["total_rounds"] == 10

    def test_enum_coercion(self):
        msg = WsMessage(type="task_stopped", task_id="task_001")
        assert isinstance(msg.type, WsMessageType)

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            WsMessage(type="unknown_event", task_id="task_001")
