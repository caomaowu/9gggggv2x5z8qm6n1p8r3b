"""
仿真模拟交易模块 — FastAPI 入口
端口: 18520
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from models.db import init_db
from engine.scheduler import KlineScheduler
from engine.task_manager import TaskManager
from api.ws_manager import WsManager
from api.routes_tasks import router as tasks_router
from api.routes_stats import router as stats_router

# ── 全局单例（由 lifespan 初始化） ──
_db = None
_scheduler: KlineScheduler | None = None
_ws_manager: WsManager | None = None
_task_manager: TaskManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db, _scheduler, _ws_manager, _task_manager

    # 启动
    _db = await init_db()
    _scheduler = KlineScheduler(buffer_seconds=settings.KLINE_BUFFER_SECONDS)
    _ws_manager = WsManager()
    _task_manager = TaskManager(_db, _scheduler, _ws_manager)

    # 崩溃恢复
    await _task_manager.recover_on_startup()

    # 后台启动调度器
    scheduler_task = asyncio.create_task(_scheduler.run())

    yield

    # 关闭
    _scheduler.stop()
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    await _db.close()


app = FastAPI(title="QuantAgent Simulation", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tasks_router)
app.include_router(stats_router)


@app.get("/")
def root():
    return {"service": "QuantAgent Simulation", "version": "0.1.0"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    if _ws_manager is None:
        await ws.close()
        return
    await _ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await _ws_manager.disconnect(ws)


# ── 直接运行入口 ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host=settings.SIM_HOST, port=settings.SIM_PORT, reload=False)
