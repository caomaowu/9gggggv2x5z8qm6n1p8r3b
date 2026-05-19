"""
回合执行器 — 核心编排：结算 → 分析 → 记录 → 押注
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import httpx

from config import settings
from engine.betting import calculate_bet, calculate_pnl
from models.db import (
    get_latest_round,
    get_task,
    get_unsettled_round,
    insert_round,
    settle_round,
    update_task_capital,
    update_task_last_kline,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def execute_round(db, task_id: str, ws_manager=None) -> dict | None:
    """
    执行一个完整回合
    """
    import logging
    _log = logging.getLogger("simulation")

    task = await get_task(db, task_id)
    if not task:
        _log.warning(f"execute_round: 任务 {task_id} 不存在")
        return None

    _log.info(f"回合开始: {task['asset']} {task['timeframe']}")

    # ── ① 结算上一局 ──
    prev_round = await get_unsettled_round(db, task_id)
    prev_result = None
    if prev_round:
        # 用当前价格判定上局结果
        settle_price = await _fetch_current_price(task["asset"])
        if settle_price is None:
            settle_price = prev_round["trigger_kline_close"] or 0
        prev_direction = prev_round["bet_direction"]
        entry_price = prev_round["trigger_kline_close"] or 0

        if prev_direction == "long":
            won = settle_price > entry_price
        elif prev_direction == "short":
            won = settle_price < entry_price
        else:
            won = False

        result = "WIN" if won else "LOSE"
        pnl = calculate_pnl(prev_direction, result, prev_round["bet_amount"], task["fee_rate"])
        new_capital = task["current_capital"] + pnl

        await settle_round(db, prev_round["id"], settle_price, result, pnl)
        await update_task_capital(db, task_id, new_capital, result)
        prev_result = {"result": result, "pnl": pnl}

        # 刷新 task
        task = await get_task(db, task_id)
        if not task:
            return None

    # ── ② 调用分析 API ──
    analyze_result = await _call_analyze_api(task["asset"], task["timeframe"])
    if analyze_result is None:
        return None

    direction = analyze_result.get("direction", "none")
    score = analyze_result.get("score", 0)
    confidence = analyze_result.get("confidence", 0)
    entry_point = analyze_result.get("entry_point")

    # 提取 3 agent 分数
    indicator_score = analyze_result.get("indicator_score")
    indicator_confidence = analyze_result.get("indicator_confidence")
    structure_score = analyze_result.get("structure_score")
    structure_confidence = analyze_result.get("structure_confidence")
    mechanics_score = analyze_result.get("mechanics_score")
    mechanics_confidence = analyze_result.get("mechanics_confidence")

    # ── ③ 确定本回合触发 K 线时间 ──
    now_ts = _now()
    trigger_kline_ts = _get_latest_kline_close(task["timeframe"])

    # ── ④ 记录 + 押注 ──
    round_id = str(uuid.uuid4())
    round_seq = (task["total_rounds"] or 0) + 1

    if direction in ("long", "short"):
        bet_amount = calculate_bet(
            task["bet_mode"], task["bet_amount"], task["bet_percent"], task["current_capital"]
        )
        if bet_amount > task["current_capital"]:
            bet_amount = task["current_capital"]
        round_status = "BET_PLACED"
        bet_direction = direction
        result_field = None
        pnl_field = None
    else:
        bet_amount = 0.0
        round_status = "SETTLED"
        bet_direction = None
        result_field = "SKIP"
        pnl_field = 0.0

    round_data = {
        "id": round_id,
        "task_id": task_id,
        "round_seq": round_seq,
        "status": round_status,
        "trigger_kline_ts": trigger_kline_ts,
        "trigger_kline_open": analyze_result.get("trigger_kline_open"),
        "trigger_kline_close": entry_point,
        "direction": direction,
        "score": score,
        "confidence": confidence,
        "entry_point": entry_point,
        "indicator_score": indicator_score,
        "indicator_confidence": indicator_confidence,
        "structure_score": structure_score,
        "structure_confidence": structure_confidence,
        "mechanics_score": mechanics_score,
        "mechanics_confidence": mechanics_confidence,
        "indicator_summary": analyze_result.get("indicator_summary"),
        "structure_summary": analyze_result.get("structure_summary"),
        "mechanics_summary": analyze_result.get("mechanics_summary"),
        "fusion_raw": analyze_result.get("fusion_raw"),
        "bet_direction": bet_direction,
        "bet_amount": bet_amount,
        "fee_amount": bet_amount * task["fee_rate"] if bet_amount > 0 else 0,
        "created_at": now_ts,
    }

    inserted_id = await insert_round(db, round_data)
    if inserted_id is None:
        return None  # 重复触发

    # 更新 task.last_kline_ts
    await update_task_last_kline(db, task_id, trigger_kline_ts)

    # 如果是 SKIP，更新资金统计
    if direction == "none":
        await update_task_capital(db, task_id, task["current_capital"], "SKIP")

    # ── ⑤ WebSocket 推送 ──
    round_data["id"] = round_id
    round_data["result"] = result_field
    round_data["pnl"] = pnl_field
    if ws_manager:
        await ws_manager.broadcast({
            "type": "round_completed",
            "task_id": task_id,
            "data": {
                "round_seq": round_seq,
                "direction": direction,
                "score": score,
                "confidence": confidence,
                "bet_amount": bet_amount,
                "prev_result": prev_result,
            },
        })

    _log.info(f"回合完成: {task['asset']} dir={direction} score={score} bet={bet_amount}")
    return round_data


# ═══════════════════════════════════════════
#  内部辅助
# ═══════════════════════════════════════════

async def _call_analyze_api(asset: str, timeframe: str) -> dict | None:
    """调用现有后端分析 API，返回标准化结果"""
    import logging
    _log = logging.getLogger("simulation")

    for attempt in range(settings.ANALYZE_RETRY_COUNT + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.ANALYZE_TIMEOUT) as client:
                resp = await client.post(
                    settings.ANALYZE_API_URL,
                    json={
                        "asset": asset,
                        "timeframe": timeframe,
                        "data_source": "quant_api",
                        "data_method": "latest",
                        "kline_count": settings.DEFAULT_KLINE_COUNT,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                _log.info(f"分析 API 调用成功: {asset} {timeframe} direction={data.get('decision',{}).get('direction','?')}")
                return _parse_analyze_response(data)
        except Exception as e:
            _log.warning(f"分析 API 调用失败 (attempt {attempt+1}/{settings.ANALYZE_RETRY_COUNT+1}): {e}")
            if attempt < settings.ANALYZE_RETRY_COUNT:
                import asyncio
                await asyncio.sleep(settings.ANALYZE_RETRY_DELAY)
    _log.error(f"分析 API 调用最终失败: {asset} {timeframe}")
    return None


def _parse_analyze_response(data: dict) -> dict:
    """从后端响应中提取标准化字段"""
    decision = data.get("decision", {})
    market_data = data.get("market_data", {}) or {}

    fusion = decision.get("fusion_raw") or market_data.get("fusion") or {}
    indicator = market_data.get("indicator_summary") or {}
    structure = market_data.get("structure_summary") or {}
    mechanics = market_data.get("mechanics_summary") or {}

    return {
        "direction": decision.get("direction") or fusion.get("direction", "none"),
        "score": decision.get("score") or fusion.get("score", 0),
        "confidence": decision.get("confidence") or fusion.get("confidence", 0),
        "entry_point": decision.get("entry_point"),
        "trigger_kline_open": None,  # API 不直接返回，用 None

        "indicator_score": indicator.get("movement_score"),
        "indicator_confidence": indicator.get("movement_confidence"),
        "structure_score": structure.get("movement_score"),
        "structure_confidence": structure.get("movement_confidence"),
        "mechanics_score": mechanics.get("movement_score"),
        "mechanics_confidence": mechanics.get("movement_confidence"),

        "indicator_summary": json.dumps(indicator) if indicator else None,
        "structure_summary": json.dumps(structure) if structure else None,
        "mechanics_summary": json.dumps(mechanics) if mechanics else None,
        "fusion_raw": json.dumps(fusion) if fusion else None,
    }


async def _fetch_current_price(asset: str) -> float | None:
    """获取当前价格（简化：复用分析 API 的最后一根 K 线收盘价）"""
    # 实际应用中可调用 OKX 行情接口，这里返回 None 让调用方使用 K 线收盘价
    return None


def _get_latest_kline_close(timeframe: str) -> str:
    """计算最近一根已收盘 K 线的收盘时间（ISO 8601）"""
    from datetime import timedelta
    from engine.scheduler import KlineScheduler

    # 上一根 K 线的收盘时间 = 下一根 K 线的收盘时间 - 周期长度
    timeframe_seconds = {
        "1m": 60, "3m": 180, "5m": 300, "15m": 900,
        "1h": 3600, "4h": 14400, "1d": 86400,
    }
    period = timeframe_seconds.get(timeframe, 3600)
    next_close_ts = KlineScheduler.calc_next_kline_close(timeframe)
    prev_close_ts = next_close_ts - period
    return datetime.fromtimestamp(prev_close_ts, tz=timezone.utc).isoformat()
