"""
任务管理器 — 多任务生命周期：创建/启动/停止/删除/崩溃恢复
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from engine.round_executor import execute_round, _fetch_current_price
from engine.scheduler import KlineScheduler
from models.db import (
    create_task as db_create_task,
    delete_task as db_delete_task,
    get_latest_round,
    get_running_tasks,
    get_task,
    get_unsettled_round,
    list_tasks,
    settle_round,
    update_task_capital,
    update_task_last_kline,
    update_task_params,
    update_task_status,
)
from engine.betting import calculate_pnl


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskManager:
    """管理所有模拟交易任务的生命周期"""

    def __init__(self, db, scheduler: KlineScheduler, ws_manager=None):
        self._db = db
        self._scheduler = scheduler
        self._ws = ws_manager
        self._active_tasks: dict[str, "asyncio.Task"] = {}

    # ── 创建 ──

    async def create_task(self, asset: str, timeframe: str,
                          bet_mode: str = "fixed", bet_amount: float = 100.0,
                          bet_percent: float | None = None,
                          fee_rate: float = 0.0,
                          initial_capital: float = 10000.0) -> dict:
        task_data = {
            "id": str(uuid.uuid4()),
            "asset": asset,
            "timeframe": timeframe,
            "status": "STOPPED",
            "bet_amount": bet_amount,
            "bet_mode": bet_mode,
            "bet_percent": bet_percent,
            "fee_rate": fee_rate,
            "initial_capital": initial_capital,
            "current_capital": initial_capital,
            "total_rounds": 0,
            "wins": 0,
            "losses": 0,
            "skips": 0,
            "best_win_streak": 0,
            "worst_lose_streak": 0,
            "current_streak": None,
            "last_kline_ts": None,
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db_create_task(self._db, task_data)
        return task_data

    # ── 启动 ──

    async def start_task(self, task_id: str) -> dict | None:
        task = await get_task(self._db, task_id)
        if not task:
            return None
        if task["status"] == "RUNNING":
            return task

        await update_task_status(self._db, task_id, "RUNNING")

        # 立即执行首轮（不用等 K 线收盘）
        self._active_tasks[task_id] = asyncio.create_task(
            self._wrap_execute_round(task_id, self._db, task_id, self._ws)
        )

        # 同时注册后续调度
        self._schedule_next(task_id, task["timeframe"])

        if self._ws:
            await self._ws.broadcast({"type": "task_started", "task_id": task_id, "data": {}})

        return await get_task(self._db, task_id)

    # ── 停止 ──

    async def stop_task(self, task_id: str) -> dict | None:
        task = await get_task(self._db, task_id)
        if not task:
            return None

        self._scheduler.cancel(task_id)
        active_task = self._active_tasks.pop(task_id, None)
        if active_task and not active_task.done():
            active_task.cancel()
        await update_task_status(self._db, task_id, "STOPPED")

        if self._ws:
            await self._ws.broadcast({"type": "task_stopped", "task_id": task_id, "data": {}})

        return await get_task(self._db, task_id)

    # ── 删除 ──

    async def delete_task(self, task_id: str) -> bool:
        task = await get_task(self._db, task_id)
        if not task:
            return False

        self._scheduler.cancel(task_id)
        active_task = self._active_tasks.pop(task_id, None)
        if active_task and not active_task.done():
            active_task.cancel()
        await db_delete_task(self._db, task_id)

        if self._ws:
            await self._ws.broadcast({"type": "task_deleted", "task_id": task_id, "data": {}})

        return True

    # ── 更新 ──

    async def update_task(self, task_id: str, **kwargs) -> dict | None:
        task = await get_task(self._db, task_id)
        if not task:
            return None

        await update_task_params(self._db, task_id, **kwargs)

        if self._ws:
            await self._ws.broadcast({"type": "task_updated", "task_id": task_id, "data": {}})

        return await get_task(self._db, task_id)

    # ── 查询 ──

    async def get_task(self, task_id: str) -> dict | None:
        return await get_task(self._db, task_id)

    async def list_tasks(self) -> list[dict]:
        return await list_tasks(self._db)

    # ── 崩溃恢复 ──

    async def recover_on_startup(self) -> None:
        """启动时恢复所有 RUNNING 任务"""
        running = await get_running_tasks(self._db)
        for task in running:
            # 结算上一局（如有）
            unsettled = await get_unsettled_round(self._db, task["id"])
            if unsettled:
                # 用实时价格作为结算价（和 execute_round 保持一致）
                settle_price = await _fetch_current_price(task["asset"])
                if settle_price is None:
                    import logging
                    logging.getLogger("simulation").warning(
                        f"恢复时无法获取当前价格，跳过结算 task={task['id']}"
                    )
                    # 不结算，直接进入调度
                else:
                    direction = unsettled["bet_direction"]
                    entry_price = unsettled.get("trigger_kline_close") or 0

                    if direction == "long":
                        won = settle_price > entry_price
                    elif direction == "short":
                        won = settle_price < entry_price
                    else:
                        won = False

                    result = "WIN" if won else "LOSE"
                    pnl = calculate_pnl(direction, result, unsettled["bet_amount"], task["fee_rate"])
                    new_capital = task["current_capital"] + pnl

                    await settle_round(self._db, unsettled["id"], settle_price, result, pnl)
                    await update_task_capital(self._db, task["id"], new_capital, result)

            # 重新入调度 + 立即执行一轮
            self._schedule_next(task["id"], task["timeframe"])
            self._active_tasks[task["id"]] = asyncio.create_task(
                self._wrap_execute_round(task["id"], self._db, task["id"], self._ws)
            )

    # ── 内部 ──

    async def _wrap_execute_round(self, task_id: str, db, inner_task_id: str, ws) -> None:
        """包装 execute_round，完成后自动清理 _active_tasks 中的引用"""
        try:
            await execute_round(db, inner_task_id, ws)
        finally:
            self._active_tasks.pop(task_id, None)

    def _schedule_next(self, task_id: str, timeframe: str) -> None:
        """计算下个 K 线收盘时间并入调度器"""
        db = self._db
        ws = self._ws

        async def callback():
            try:
                await execute_round(db, task_id, ws)
            except Exception:
                import logging
                logging.getLogger("simulation").exception(f"回合执行异常 task={task_id}")
            finally:
                # 无论成败都继续调度下一个
                self._schedule_next(task_id, timeframe)

        next_close = KlineScheduler.calc_next_kline_close(timeframe)
        self._scheduler.schedule(next_close, task_id, callback)
