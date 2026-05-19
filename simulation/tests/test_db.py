"""tests for simulation.models.db"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from simulation.models.db import (
    create_task,
    delete_task,
    get_equity_curve,
    get_latest_round,
    get_round,
    get_rounds_by_task,
    get_running_tasks,
    get_task,
    get_task_stats,
    get_unsettled_round,
    init_db,
    insert_round,
    list_tasks,
    settle_round,
    update_task_capital,
    update_task_last_kline,
    update_task_status,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_data(**overrides) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "asset": "BTC-USDT",
        "timeframe": "4h",
        "status": "STOPPED",
        "bet_amount": 100.0,
        "bet_mode": "fixed",
        "bet_percent": None,
        "fee_rate": 0.002,
        "initial_capital": 10000.0,
        "current_capital": 10000.0,
        "created_at": _now(),
        "updated_at": _now(),
        **overrides,
    }


def _round_data(task_id: str, **overrides) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "round_seq": 1,
        "status": "BET_PLACED",
        "trigger_kline_ts": "2025-05-19T12:00:00+00:00",
        "trigger_kline_open": None,
        "trigger_kline_close": 67500.0,
        "direction": "long",
        "score": 0.52,
        "confidence": 0.71,
        "entry_point": 67500.0,
        "indicator_score": 0.3,
        "indicator_confidence": 0.6,
        "structure_score": 0.5,
        "structure_confidence": 0.8,
        "mechanics_score": -0.1,
        "mechanics_confidence": 0.4,
        "indicator_summary": None,
        "structure_summary": None,
        "mechanics_summary": None,
        "fusion_raw": None,
        "bet_direction": "long",
        "bet_amount": 100.0,
        "fee_amount": 0.0,
        "created_at": _now(),
        **overrides,
    }


# ── 数据库初始化 ──

@pytest.mark.asyncio
async def test_init_db_creates_tables(tmp_db_path):
    db = await init_db(tmp_db_path)
    async with db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name") as cur:
        tables = [row["name"] for row in await cur.fetchall()]
    assert "tasks" in tables
    assert "rounds" in tables
    await db.close()


@pytest.mark.asyncio
async def test_init_db_creates_indexes(tmp_db_path):
    db = await init_db(tmp_db_path)
    async with db.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name") as cur:
        indexes = [row["name"] for row in await cur.fetchall()]
    assert "idx_rounds_task_id" in indexes
    assert "idx_rounds_task_seq" in indexes
    assert "idx_rounds_trigger" in indexes
    await db.close()


# ── Task CRUD ──

@pytest.mark.asyncio
async def test_create_and_get_task(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    task = await get_task(db, tid)
    assert task is not None
    assert task["asset"] == "BTC-USDT"
    assert task["timeframe"] == "4h"
    assert task["status"] == "STOPPED"
    await db.close()


@pytest.mark.asyncio
async def test_list_tasks(tmp_db_path):
    db = await init_db(tmp_db_path)
    await create_task(db, _task_data(id="t1", asset="BTC-USDT"))
    await create_task(db, _task_data(id="t2", asset="ETH-USDT"))
    tasks = await list_tasks(db)
    assert len(tasks) == 2
    await db.close()


@pytest.mark.asyncio
async def test_get_task_not_found(tmp_db_path):
    db = await init_db(tmp_db_path)
    task = await get_task(db, "nonexistent")
    assert task is None
    await db.close()


@pytest.mark.asyncio
async def test_update_task_status(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    await update_task_status(db, tid, "RUNNING")
    task = await get_task(db, tid)
    assert task["status"] == "RUNNING"
    await db.close()


@pytest.mark.asyncio
async def test_get_running_tasks(tmp_db_path):
    db = await init_db(tmp_db_path)
    await create_task(db, _task_data(id="t1", status="RUNNING"))
    await create_task(db, _task_data(id="t2", status="STOPPED"))
    await create_task(db, _task_data(id="t3", status="RUNNING"))
    running = await get_running_tasks(db)
    assert len(running) == 2
    ids = {t["id"] for t in running}
    assert ids == {"t1", "t3"}
    await db.close()


@pytest.mark.asyncio
async def test_delete_task(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    await insert_round(db, _round_data(tid))
    await delete_task(db, tid)
    assert await get_task(db, tid) is None
    rounds = await get_rounds_by_task(db, tid)
    assert len(rounds) == 0
    await db.close()


# ── update_task_capital + streak ──

@pytest.mark.asyncio
async def test_update_task_capital_win(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    await update_task_capital(db, tid, 10100.0, "WIN")
    task = await get_task(db, tid)
    assert task["current_capital"] == 10100.0
    assert task["wins"] == 1
    assert task["losses"] == 0
    assert task["total_rounds"] == 1
    assert task["current_streak"] == "W1"
    assert task["best_win_streak"] == 1
    await db.close()


@pytest.mark.asyncio
async def test_update_task_capital_lose(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    await update_task_capital(db, tid, 9900.0, "LOSE")
    task = await get_task(db, tid)
    assert task["losses"] == 1
    assert task["current_streak"] == "L1"
    assert task["worst_lose_streak"] == 1
    await db.close()


@pytest.mark.asyncio
async def test_update_task_capital_streak_wins(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    for i in range(3):
        await update_task_capital(db, tid, 10000.0 + (i + 1) * 100, "WIN")
    task = await get_task(db, tid)
    assert task["current_streak"] == "W3"
    assert task["best_win_streak"] == 3
    await db.close()


@pytest.mark.asyncio
async def test_update_task_capital_streak_break(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    await update_task_capital(db, tid, 10100.0, "WIN")
    await update_task_capital(db, tid, 9900.0, "LOSE")
    task = await get_task(db, tid)
    assert task["current_streak"] == "L1"
    assert task["best_win_streak"] == 1
    await db.close()


@pytest.mark.asyncio
async def test_update_task_capital_skip(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    await update_task_capital(db, tid, 10000.0, "SKIP")
    task = await get_task(db, tid)
    assert task["skips"] == 1
    assert task["current_streak"] is None
    assert task["total_rounds"] == 1
    await db.close()


@pytest.mark.asyncio
async def test_update_task_last_kline(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    ts = "2025-05-19T16:00:00+00:00"
    await update_task_last_kline(db, tid, ts)
    task = await get_task(db, tid)
    assert task["last_kline_ts"] == ts
    await db.close()


# ── Round CRUD ──

@pytest.mark.asyncio
async def test_insert_and_get_round(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    rid = await insert_round(db, _round_data(tid))
    assert rid is not None
    round_ = await get_round(db, rid)
    assert round_ is not None
    assert round_["task_id"] == tid
    assert round_["direction"] == "long"
    await db.close()


@pytest.mark.asyncio
async def test_insert_round_duplicate_returns_none(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    r1 = _round_data(tid, id="r1", trigger_kline_ts="2025-05-19T12:00:00+00:00")
    r2 = _round_data(tid, id="r2", trigger_kline_ts="2025-05-19T12:00:00+00:00")  # same ts
    rid1 = await insert_round(db, r1)
    rid2 = await insert_round(db, r2)
    assert rid1 == "r1"
    assert rid2 is None
    await db.close()


@pytest.mark.asyncio
async def test_get_latest_round(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    await insert_round(db, _round_data(tid, id="r1", round_seq=1))
    await insert_round(db, _round_data(tid, id="r2", round_seq=2, trigger_kline_ts="2025-05-19T16:00:00+00:00"))
    latest = await get_latest_round(db, tid)
    assert latest is not None
    assert latest["round_seq"] == 2
    await db.close()


@pytest.mark.asyncio
async def test_get_latest_round_none_for_empty_task(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    assert await get_latest_round(db, tid) is None
    await db.close()


@pytest.mark.asyncio
async def test_get_rounds_by_task_pagination(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    for i in range(5):
        await insert_round(db, _round_data(tid, id=f"r{i}", round_seq=i + 1, trigger_kline_ts=f"2025-05-{19+i}T12:00:00+00:00"))
    page1 = await get_rounds_by_task(db, tid, offset=0, limit=2)
    assert len(page1) == 2
    assert page1[0]["round_seq"] == 5  # DESC order
    page2 = await get_rounds_by_task(db, tid, offset=2, limit=2)
    assert len(page2) == 2
    assert page2[0]["round_seq"] == 3
    await db.close()


@pytest.mark.asyncio
async def test_get_unsettled_round(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    await insert_round(db, _round_data(tid, id="r1", round_seq=1, status="SETTLED", trigger_kline_ts="2025-05-19T08:00:00+00:00"))
    await insert_round(db, _round_data(tid, id="r2", round_seq=2, trigger_kline_ts="2025-05-19T12:00:00+00:00"))
    unsettled = await get_unsettled_round(db, tid)
    assert unsettled is not None
    assert unsettled["id"] == "r2"
    await db.close()


@pytest.mark.asyncio
async def test_settle_round(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    rid = await insert_round(db, _round_data(tid))
    await settle_round(db, rid, 67800.0, "WIN", 100.0)
    r = await get_round(db, rid)
    assert r["status"] == "SETTLED"
    assert r["settle_price"] == 67800.0
    assert r["result"] == "WIN"
    assert r["pnl"] == 100.0
    assert r["settled_at"] is not None
    await db.close()


# ── 统计 ──

@pytest.mark.asyncio
async def test_get_equity_curve(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    await insert_round(db, _round_data(tid, id="r1", round_seq=1, trigger_kline_ts="2025-05-19T08:00:00+00:00"))
    await settle_round(db, "r1", 67800.0, "WIN", 100.0)
    await insert_round(db, _round_data(tid, id="r2", round_seq=2, trigger_kline_ts="2025-05-19T12:00:00+00:00"))
    await settle_round(db, "r2", 67700.0, "LOSE", -100.0)
    curve = await get_equity_curve(db, tid)
    assert len(curve) == 2
    assert curve[0]["cumulative_pnl"] == 100.0
    assert curve[1]["cumulative_pnl"] == 0.0
    await db.close()


@pytest.mark.asyncio
async def test_get_equity_curve_empty(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    curve = await get_equity_curve(db, tid)
    assert curve == []
    await db.close()


@pytest.mark.asyncio
async def test_get_task_stats(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    # 模拟完整回合：插入 → 结算 → 更新资金
    await insert_round(db, _round_data(tid, id="r1", round_seq=1, trigger_kline_ts="2025-05-19T04:00:00+00:00"))
    await settle_round(db, "r1", 67800.0, "WIN", 100.0)
    await update_task_capital(db, tid, 10100.0, "WIN")
    await insert_round(db, _round_data(tid, id="r2", round_seq=2, trigger_kline_ts="2025-05-19T08:00:00+00:00"))
    await settle_round(db, "r2", 67900.0, "WIN", 100.0)
    await update_task_capital(db, tid, 10200.0, "WIN")
    await insert_round(db, _round_data(tid, id="r3", round_seq=3, trigger_kline_ts="2025-05-19T12:00:00+00:00"))
    await settle_round(db, "r3", 67800.0, "LOSE", -100.0)
    await update_task_capital(db, tid, 10100.0, "LOSE")
    stats = await get_task_stats(db, tid)
    assert stats["total_rounds"] == 3
    assert stats["wins"] == 2
    assert stats["losses"] == 1
    assert stats["win_rate"] == pytest.approx(0.6667, abs=0.0001)
    assert stats["current_capital"] == 10100.0
    assert stats["roi"] == pytest.approx(0.01)
    assert stats["total_pnl"] == 100.0
    await db.close()


@pytest.mark.asyncio
async def test_get_task_stats_empty(tmp_db_path):
    db = await init_db(tmp_db_path)
    data = _task_data()
    tid = await create_task(db, data)
    stats = await get_task_stats(db, tid)
    assert stats["total_rounds"] == 0
    assert stats["win_rate"] == 0.0
    await db.close()
