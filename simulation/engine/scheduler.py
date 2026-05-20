"""K-line close-time scheduler using asyncio + heapq.

Provides precise scheduling of round-execution callbacks aligned to
UTC K-line close times.  Callbacks fire *buffer_seconds* after the
nominal close to allow the data API time to confirm the closed candle.
"""

from __future__ import annotations

import asyncio
import heapq
import math
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Awaitable  # noqa: UP035  # Awaitable not in collections.abc until 3.13

# ---------------------------------------------------------------------------
# Timeframe → seconds mapping
# ---------------------------------------------------------------------------

TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


# ---------------------------------------------------------------------------
# KlineScheduler
# ---------------------------------------------------------------------------


class KlineScheduler:
    """Manages scheduled events via an asyncio-friendly priority queue.

    Each event is identified by a *task_id*.  Events whose *task_id* has been
    cancelled are silently skipped.  Callbacks are invoked via
    ``asyncio.create_task`` so errors in a callback never crash the scheduler.
    """

    def __init__(self, buffer_seconds: int = 30) -> None:
        """*buffer_seconds* – delay after K-line close before firing."""
        self._heap: list[tuple[float, str, Callable[[], Awaitable[None]]]] = []
        self._cancelled: set[str] = set()
        self._event = asyncio.Event()
        self._running = False
        self._buffer = buffer_seconds
        # threading.Lock 而非 asyncio.Lock，因为 schedule()/cancel() 是同步方法
        # （被 _schedule_next 等同步调用方使用），不能使用 async with 语法。
        # 在单线程 asyncio 事件循环中，只要不在持有锁期间 await，threading.Lock 完全安全。
        self._lock = threading.Lock()

    # -- public API ---------------------------------------------------------

    def schedule(
        self,
        trigger_ts: float,
        task_id: str,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        """Schedule *callback* to fire at *trigger_ts* + *buffer_seconds*.

        Safe to call from any coroutine, including from within a callback
        (re-entrant).
        """
        fire_ts = trigger_ts + self._buffer
        with self._lock:
            heapq.heappush(self._heap, (fire_ts, task_id, callback))
        self._event.set()

    def cancel(self, task_id: str) -> None:
        """Cancel all pending and future events for *task_id*.

        主动从堆中移除该任务的所有条目，防止已取消事件在堆中累积（内存泄漏），
        也避免 run() 被已取消事件频繁唤醒。
        """
        with self._lock:
            self._cancelled.add(task_id)
            # 过滤堆中该任务的所有条目并重建堆
            self._heap = [
                (ts, tid, cb)
                for ts, tid, cb in self._heap
                if tid != task_id
            ]
            heapq.heapify(self._heap)
        # 唤醒 run()：堆顶可能已变化（新堆顶时间不同、或堆变空）
        self._event.set()

    async def run(self) -> None:
        """Main scheduling loop.  Exits when :meth:`stop` is called.

        临界区（读堆顶 / 检查 cancelled / pop）用 self._lock 保护；
        锁在 await 前释放，避免跨协程持有锁。
        """
        self._running = True
        while self._running:
            # --- 等待堆非空 ------------------------------------------------
            while not self._heap:
                if not self._running:
                    return
                await self._event.wait()
                self._event.clear()

            # --- 临界区：检查堆顶事件 --------------------------------------
            with self._lock:
                # cancel() 可能清空了堆，需要重新检查
                if not self._heap:
                    continue

                fire_ts, task_id, callback = self._heap[0]
                now = time.time()

                if task_id in self._cancelled:
                    heapq.heappop(self._heap)
                    continue

                if fire_ts <= now:
                    heapq.heappop(self._heap)
                    asyncio.create_task(self._safe_fire(task_id, callback))
                    continue

                # fire_ts > now：释放锁后再等待超时
                wait_seconds = fire_ts - now

            try:
                await asyncio.wait_for(
                    self._event.wait(),
                    timeout=wait_seconds,
                )
            except TimeoutError:
                pass
            self._event.clear()

    def stop(self) -> None:
        """Signal :meth:`run` to exit gracefully at the next iteration."""
        self._running = False
        self._event.set()

    # -- static helpers -----------------------------------------------------

    @staticmethod
    def calc_next_kline_close(
        timeframe: str,
        from_ts: float | None = None,
    ) -> float:
        """Return the Unix timestamp of the next K-line close for *timeframe*.

        Parameters
        ----------
        timeframe:
            One of ``"1m"``, ``"3m"``, ``"5m"``, ``"15m"``, ``"1h"``,
            ``"4h"``, ``"1d"``.
        from_ts:
            Reference timestamp (UTC).  Defaults to ``time.time()``.

        Returns
        -------
        float
            Unix seconds of the next aligned close.  Even when *from_ts* falls
            exactly on a boundary the **next** boundary is returned.

        Examples
        --------
        >>> ts = datetime(2025, 5, 19, 14, 35, 0, tzinfo=UTC).timestamp()
        >>> KlineScheduler.calc_next_kline_close("1h", ts)
        # → 15:00 UTC
        """
        period = TIMEFRAME_SECONDS[timeframe]
        ts = from_ts if from_ts is not None else time.time()
        return (math.floor(ts / period) + 1) * period

    @staticmethod
    def format_close_time(close_ts: float) -> str:
        """Return an ISO-8601 UTC string for *close_ts* (for logging/debug)."""
        return datetime.fromtimestamp(close_ts, tz=UTC).isoformat()

    # -- internals ----------------------------------------------------------

    async def _safe_fire(
        self,
        task_id: str,
        callback: Callable[[], Awaitable[None]],
    ) -> None:
        """Invoke *callback*, swallowing any exception.

        A second cancellation check is done here to catch races where
        :meth:`cancel` is called after the event was popped but before the
        task actually executes.
        """
        if task_id in self._cancelled:
            return
        try:
            await callback()
        except Exception as e:
            import logging
            logging.getLogger("simulation").error(f"调度器回调异常 task={task_id}: {e}", exc_info=True)
