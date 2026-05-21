"""
任务管理器 — 多任务生命周期：创建/启动/停止/删除/崩溃恢复
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

from config import settings
from engine.round_executor import execute_round, pre_analyze, _fetch_current_price
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
        self._pre_analysis: dict[str, dict] = {}  # task_id → 预分析结果（用于双回调间传递）

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
        """调度下一轮：预分析（收盘前） + 执行（收盘时）双回调"""
        next_close = KlineScheduler.calc_next_kline_close(timeframe)
        offset = settings.PRE_ANALYZE_OFFSETS.get(timeframe, 60)
        pre_trigger = next_close - offset

        # ① 预分析事件：收盘前 offset 秒触发
        if pre_trigger > time.time():
            async def pre_callback():
                await self._wrap_pre_analyze(task_id)
            self._scheduler.schedule(pre_trigger, task_id, pre_callback)

        # ② 执行事件：收盘时触发（沿用 KLINE_BUFFER_SECONDS 延迟）
        async def exec_callback():
            try:
                await self._wrap_scheduled_round(task_id)
            except Exception:
                import logging
                logging.getLogger("simulation").exception(f"回合执行异常 task={task_id}")
            finally:
                self._schedule_next(task_id, timeframe)

        self._scheduler.schedule(next_close, task_id, exec_callback)

    # ── 预分析回调 ──

    async def _wrap_pre_analyze(self, task_id: str) -> None:
        """收盘前预分析：调用分析 API，结果存入 _pre_analysis。

        成功存入完整分析字典，失败存入空字典 {}。
        如果任务已不在运行状态，静默跳过。
        """
        import logging
        _log = logging.getLogger("simulation")

        task = await get_task(self._db, task_id)
        if not task or task["status"] != "RUNNING":
            return

        _log.info(f"预分析开始: {task['asset']} {task['timeframe']} task={task_id}")
        result = await pre_analyze(task["asset"], task["timeframe"])
        self._pre_analysis[task_id] = result
        if result:
            _log.info(f"预分析完成: {task['asset']} dir={result.get('direction', '?')} task={task_id}")
        else:
            _log.warning(f"预分析失败（收盘时将记录 SKIP）: {task['asset']} task={task_id}")

    # ── 收盘执行回调 ──

    async def _wrap_scheduled_round(self, task_id: str) -> None:
        """收盘时执行回合，消费 _pre_analysis 中的预分析结果。

        - 若预分析已执行（key 存在）：传入结果，跳过 API 调用
        - 若预分析未执行（key 不存在）：传入 None，execute_round 自行调 API（回退）
        """
        import logging
        _log = logging.getLogger("simulation")

        task = await get_task(self._db, task_id)
        if not task or task["status"] != "RUNNING":
            self._pre_analysis.pop(task_id, None)
            return

        pre_result = self._pre_analysis.pop(task_id, None)
        if pre_result is None:
            _log.warning(f"预分析结果缺失（未调度或异常），回退到同步分析 task={task_id}")
        elif not pre_result:
            _log.warning(f"预分析失败，本轮将记录 SKIP task={task_id}")

        # pre_result:
        #   None  → execute_round 自行调用分析 API（回退）
        #   {}    → execute_round 识别 direction="none" → 记录 SKIP 回合
        #   {...} → execute_round 使用预分析结果，零等待
        await execute_round(self._db, task_id, self._ws, analyze_result=pre_result)
