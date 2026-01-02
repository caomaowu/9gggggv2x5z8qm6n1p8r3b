from fastapi import APIRouter
from app.api.v1.endpoints import market, analyze, ws, system, export

api_router = APIRouter()
api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(ws.router, prefix="/ws", tags=["websocket"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
