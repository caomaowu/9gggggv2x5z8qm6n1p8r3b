"""
统计 & 交易日记 REST API
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from models.schemas import EquityPoint, RoundListResponse, RoundResponse, StatsResponse
from models.db import get_equity_curve, get_rounds_by_task, get_round_count, get_task_stats, get_task

router = APIRouter(prefix="/api/tasks", tags=["stats"])


def _get_db():
    """由 server.py 在启动时注入"""
    from server import _db
    return _db


@router.get("/{task_id}/stats", response_model=StatsResponse)
async def task_stats(task_id: str, db=Depends(_get_db)):
    if not await get_task(db, task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    stats = await get_task_stats(db, task_id)
    return StatsResponse(**stats)


@router.get("/{task_id}/equity", response_model=list[EquityPoint])
async def task_equity(task_id: str, db=Depends(_get_db)):
    if not await get_task(db, task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    points = await get_equity_curve(db, task_id)
    return [EquityPoint(**p) for p in points]


@router.get("/{task_id}/rounds", response_model=RoundListResponse)
async def task_rounds(
    task_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db=Depends(_get_db),
):
    if not await get_task(db, task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    rounds = await get_rounds_by_task(db, task_id, offset=offset, limit=limit)
    total = await get_round_count(db, task_id)
    return RoundListResponse(
        rounds=[RoundResponse(**r) for r in rounds],
        total=total,
        offset=offset,
        limit=limit,
    )
