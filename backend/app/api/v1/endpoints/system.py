from fastapi import APIRouter, HTTPException, Body
from app.utils.temp_file_manager import cleanup_all_temp_files, cleanup_exports_files
from app.core.config import config
from app.core.preferences import preferences_manager
from typing import Dict, Any

router = APIRouter()

@router.get("/llm-config")
async def get_llm_config():
    """
    获取当前 LLM 配置和所有可用选项
    """
    try:
        config_data = config.get_current_config()
        
        # 增强返回数据，直接按 provider 分组返回模型列表
        # 这样前端就不需要瞎猜或者显示所有模型了
        # 结构: { "openai": ["gpt-4", ...], "modelscope": [...] }
        agent_models_map = {}
        graph_models_map = {}
        
        providers = config.get_all_providers()
        for p in providers:
            p_id = p["id"]
            agent_models_map[p_id] = config.get_available_models(provider=p_id, role="agent")
            graph_models_map[p_id] = config.get_available_models(provider=p_id, role="graph")
            
        return {
            **config_data,
            "agent_models_map": agent_models_map,
            "graph_models_map": graph_models_map,
            "model_preferences": preferences_manager.get_all_model_temperatures()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/llm-config")
async def update_llm_config(
    agent_provider: str = Body(..., embed=True),
    agent_model: str = Body(..., embed=True),
    agent_temperature: float = Body(0.1, embed=True),
    graph_provider: str = Body(..., embed=True),
    graph_model: str = Body(..., embed=True),
    graph_temperature: float = Body(0.1, embed=True)
):
    """
    更新 LLM 配置并持久化到 .env 文件
    同时更新模型温度偏好
    """
    try:
        # Update Agent Config
        config.set_agent_provider(agent_provider, agent_model, agent_temperature, persist=True)
        # Save preference
        if agent_model:
            preferences_manager.set_model_temperature(agent_model, agent_temperature)
        
        # Update Graph Config
        config.set_graph_provider(graph_provider, graph_model, graph_temperature, persist=True)
        # Save preference
        if graph_model:
             preferences_manager.set_model_temperature(graph_model, graph_temperature)
        
        return {
            "status": "success", 
            "message": "Configuration updated and persisted to .env",
            "current_config": config.get_current_config(),
            "model_preferences": preferences_manager.get_all_model_temperatures()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
