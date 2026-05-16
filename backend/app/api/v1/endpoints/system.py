from fastapi import APIRouter, HTTPException, Body
from app.utils.temp_file_manager import cleanup_all_temp_files, cleanup_exports_files
from app.core.config import settings, reload_config
from app.core.providers import PROVIDERS, get_available_models
from app.utils.env_manager import update_env_config
from pydantic import BaseModel
from typing import List, Optional
import os

router = APIRouter()

class LLMConfigUpdate(BaseModel):
    agent_provider: Optional[str] = None
    agent_model: Optional[str] = None
    agent_temperature: Optional[float] = None
    graph_provider: Optional[str] = None
    graph_model: Optional[str] = None
    graph_temperature: Optional[float] = None
    decision_agent_version: Optional[str] = None
    # brale per-agent override
    indicator_provider: Optional[str] = None
    indicator_model: Optional[str] = None
    indicator_temperature: Optional[float] = None
    structure_provider: Optional[str] = None
    structure_model: Optional[str] = None
    structure_temperature: Optional[float] = None
    mechanics_provider: Optional[str] = None
    mechanics_model: Optional[str] = None
    mechanics_temperature: Optional[float] = None

class ThinkingModeUpdate(BaseModel):
    indicator_thinking_mode: Optional[bool] = None
    pattern_thinking_mode: Optional[bool] = None
    trend_thinking_mode: Optional[bool] = None
    decision_thinking_mode: Optional[bool] = None
    
    # 推理深度配置
    indicator_reasoning_effort: Optional[str] = None
    pattern_reasoning_effort: Optional[str] = None
    trend_reasoning_effort: Optional[str] = None
    decision_reasoning_effort: Optional[str] = None

@router.get("/thinking-mode")
async def get_thinking_mode():
    """获取思考模式配置"""
    return {
        "indicator": settings.INDICATOR_THINKING_MODE,
        "pattern": settings.PATTERN_THINKING_MODE,
        "trend": settings.TREND_THINKING_MODE,
        "decision": settings.DECISION_THINKING_MODE,
        # 返回推理深度配置
        "indicator_effort": settings.INDICATOR_REASONING_EFFORT,
        "pattern_effort": settings.PATTERN_REASONING_EFFORT,
        "trend_effort": settings.TREND_REASONING_EFFORT,
        "decision_effort": settings.DECISION_REASONING_EFFORT
    }

@router.post("/thinking-mode")
async def update_thinking_mode(config: ThinkingModeUpdate):
    """更新思考模式配置"""
    try:
        updates = {}
        if config.indicator_thinking_mode is not None:
            updates["INDICATOR_THINKING_MODE"] = str(config.indicator_thinking_mode)
        if config.pattern_thinking_mode is not None:
            updates["PATTERN_THINKING_MODE"] = str(config.pattern_thinking_mode)
        if config.trend_thinking_mode is not None:
            updates["TREND_THINKING_MODE"] = str(config.trend_thinking_mode)
        if config.decision_thinking_mode is not None:
            updates["DECISION_THINKING_MODE"] = str(config.decision_thinking_mode)
            
        # 更新推理深度
        if config.indicator_reasoning_effort is not None:
            updates["INDICATOR_REASONING_EFFORT"] = config.indicator_reasoning_effort
        if config.pattern_reasoning_effort is not None:
            updates["PATTERN_REASONING_EFFORT"] = config.pattern_reasoning_effort
        if config.trend_reasoning_effort is not None:
            updates["TREND_REASONING_EFFORT"] = config.trend_reasoning_effort
        if config.decision_reasoning_effort is not None:
            updates["DECISION_REASONING_EFFORT"] = config.decision_reasoning_effort

        if updates:
            update_env_config(updates)
            reload_config()
            
        return {
            "status": "success", 
            "message": "思考模式配置已更新",
            "current": await get_thinking_mode()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update thinking mode: {str(e)}")

@router.get("/llm-config")
async def get_llm_config():
    """
    获取当前的 LLM 配置和所有可用选项
    """
    try:
        # 获取所有 providers 的详细信息
        providers_info = {}
        for key, info in PROVIDERS.items():
            providers_info[key] = {
                "name": info["name"],
                "agent_models": info.get("agent_models", []),
                "graph_models": info.get("graph_models", [])
            }
            
        return {
            "current": {
                "agent_provider": settings.AGENT_PROVIDER,
                "agent_model": settings.AGENT_MODEL,
                "agent_temperature": settings.AGENT_TEMPERATURE,
                "graph_provider": settings.GRAPH_PROVIDER,
                "graph_model": settings.GRAPH_MODEL,
                "graph_temperature": settings.GRAPH_TEMPERATURE,
                "decision_agent_version": settings.DECISION_AGENT_VERSION,
                # brale per-agent
                "indicator_provider": settings.BRALE_INDICATOR_PROVIDER,
                "indicator_model": settings.BRALE_INDICATOR_MODEL,
                "indicator_temperature": settings.BRALE_INDICATOR_TEMPERATURE,
                "structure_provider": settings.BRALE_STRUCTURE_PROVIDER,
                "structure_model": settings.BRALE_STRUCTURE_MODEL,
                "structure_temperature": settings.BRALE_STRUCTURE_TEMPERATURE,
                "mechanics_provider": settings.BRALE_MECHANICS_PROVIDER,
                "mechanics_model": settings.BRALE_MECHANICS_MODEL,
                "mechanics_temperature": settings.BRALE_MECHANICS_TEMPERATURE,
            },
            "options": {
                "providers": providers_info,
                "decision_versions": [
                    {"id": "original", "name": "Original (Classic HFT)"},
                    {"id": "lite", "name": "Lite (Fast & Intuitive)"}
                ]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/llm-config")
async def update_llm_config(config: LLMConfigUpdate):
    """
    更新 LLM 配置并保存到 .env 文件
    """
    try:
        # 准备要更新的键值对
        updates = {}
        if config.agent_provider is not None: updates["AGENT_PROVIDER"] = config.agent_provider
        if config.agent_model is not None: updates["AGENT_MODEL"] = config.agent_model
        if config.agent_temperature is not None: updates["AGENT_TEMPERATURE"] = str(config.agent_temperature)
        if config.graph_provider is not None: updates["GRAPH_PROVIDER"] = config.graph_provider
        if config.graph_model is not None: updates["GRAPH_MODEL"] = config.graph_model
        if config.graph_temperature is not None: updates["GRAPH_TEMPERATURE"] = str(config.graph_temperature)
        if config.decision_agent_version is not None: updates["DECISION_AGENT_VERSION"] = config.decision_agent_version
        # brale per-agent
        if config.indicator_provider is not None: updates["BRALE_INDICATOR_PROVIDER"] = config.indicator_provider
        if config.indicator_model is not None: updates["BRALE_INDICATOR_MODEL"] = config.indicator_model
        if config.indicator_temperature is not None: updates["BRALE_INDICATOR_TEMPERATURE"] = str(config.indicator_temperature)
        if config.structure_provider is not None: updates["BRALE_STRUCTURE_PROVIDER"] = config.structure_provider
        if config.structure_model is not None: updates["BRALE_STRUCTURE_MODEL"] = config.structure_model
        if config.structure_temperature is not None: updates["BRALE_STRUCTURE_TEMPERATURE"] = str(config.structure_temperature)
        if config.mechanics_provider is not None: updates["BRALE_MECHANICS_PROVIDER"] = config.mechanics_provider
        if config.mechanics_model is not None: updates["BRALE_MECHANICS_MODEL"] = config.mechanics_model
        if config.mechanics_temperature is not None: updates["BRALE_MECHANICS_TEMPERATURE"] = str(config.mechanics_temperature)

        if updates:
            update_env_config(updates)
            # 重新加载配置
            reload_config()

        return {
            "status": "success",
            "message": "配置已更新并重载",
            "current": {
                "agent_provider": settings.AGENT_PROVIDER,
                "agent_model": settings.AGENT_MODEL,
                "graph_provider": settings.GRAPH_PROVIDER,
                "graph_model": settings.GRAPH_MODEL,
                "decision_agent_version": settings.DECISION_AGENT_VERSION,
                "indicator_provider": settings.BRALE_INDICATOR_PROVIDER,
                "indicator_model": settings.BRALE_INDICATOR_MODEL,
                "indicator_temperature": settings.BRALE_INDICATOR_TEMPERATURE,
                "structure_provider": settings.BRALE_STRUCTURE_PROVIDER,
                "structure_model": settings.BRALE_STRUCTURE_MODEL,
                "structure_temperature": settings.BRALE_STRUCTURE_TEMPERATURE,
                "mechanics_provider": settings.BRALE_MECHANICS_PROVIDER,
                "mechanics_model": settings.BRALE_MECHANICS_MODEL,
                "mechanics_temperature": settings.BRALE_MECHANICS_TEMPERATURE,
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

@router.post("/clear-cache")
async def clear_system_cache():
    """
    清除系统临时文件（图表、CSV记录等）
    """
    try:
        count = cleanup_all_temp_files()
        return {"status": "success", "message": f"成功清理 {count} 个临时文件", "cleaned_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear-exports")
async def clear_exports():
    """
    清除 exports 文件夹下的所有内容
    """
    try:
        count = cleanup_exports_files()
        return {"status": "success", "message": f"成功清理 {count} 个导出项目", "cleaned_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear-history")
async def clear_history():
    """
    清除 data/history 下的所有历史记录数据
    """
    try:
        from app.services.history_service import history_service
        count = history_service.clear_all_history()
        return {"status": "success", "message": f"成功清理 {count} 条历史记录数据", "cleaned_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reload-config")
async def reload_config():
    """
    手动重新加载配置（.env 文件）
    """
    try:
        from app.core.config import reload_config, settings
        reload_config()
        return {
            "status": "success",
            "message": "配置重新加载成功",
            "current_config": {
                "agent_provider": settings.AGENT_PROVIDER,
                "agent_model": settings.AGENT_MODEL,
                "agent_temperature": settings.AGENT_TEMPERATURE,
                "graph_provider": settings.GRAPH_PROVIDER,
                "graph_model": settings.GRAPH_MODEL,
                "graph_temperature": settings.GRAPH_TEMPERATURE,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置重新加载失败: {str(e)}")
