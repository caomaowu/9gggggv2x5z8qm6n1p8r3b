from fastapi import APIRouter
from app.api.v1.endpoints import market, analyze, ws, system, export, auth
from app.core.providers import PROVIDERS

api_router = APIRouter()


@api_router.get("/models")
async def list_available_models():
    """
    返回所有可用的大语言模型列表，供模拟交易等下游系统选择。
    返回格式: [{"provider": "modelscope", "provider_label": "ModelScope", "model": "Qwen/..."}, ...]
    """
    models = []
    for provider_key, cfg in PROVIDERS.items():
        for model in cfg.get("agent_models", []):
            models.append({
                "provider": provider_key,
                "provider_label": cfg["name"],
                "model": model,
            })
    return {"models": models}


api_router.include_router(market.router, prefix="/market", tags=["market"])
api_router.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(ws.router, prefix="/ws", tags=["websocket"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
