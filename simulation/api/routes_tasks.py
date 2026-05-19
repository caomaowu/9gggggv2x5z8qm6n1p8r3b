"""
任务管理 REST API
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from models.schemas import TaskCreateRequest, TaskResponse
from engine.task_manager import TaskManager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_task_manager() -> TaskManager:
    """由 server.py 在启动时注入"""
    from server import _task_manager
    return _task_manager


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(req: TaskCreateRequest, tm: TaskManager = Depends(get_task_manager)):
    task = await tm.create_task(
        asset=req.asset,
        timeframe=req.timeframe,
        bet_mode=req.bet_mode.value,
        bet_amount=req.bet_amount,
        bet_percent=req.bet_percent,
        fee_rate=req.fee_rate,
        initial_capital=req.initial_capital,
    )
    return TaskResponse(**task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(tm: TaskManager = Depends(get_task_manager)):
    tasks = await tm.list_tasks()
    return [TaskResponse(**t) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, tm: TaskManager = Depends(get_task_manager)):
    task = await tm.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskResponse(**task)


@router.post("/{task_id}/start", response_model=TaskResponse)
async def start_task(task_id: str, tm: TaskManager = Depends(get_task_manager)):
    task = await tm.start_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskResponse(**task)


@router.post("/{task_id}/stop", response_model=TaskResponse)
async def stop_task(task_id: str, tm: TaskManager = Depends(get_task_manager)):
    task = await tm.stop_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskResponse(**task)


@router.delete("/{task_id}")
async def delete_task(task_id: str, tm: TaskManager = Depends(get_task_manager)):
    ok = await tm.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"ok": True}
