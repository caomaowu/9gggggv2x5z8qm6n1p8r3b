from fastapi import APIRouter, HTTPException, Body
from app.utils.temp_file_manager import cleanup_all_temp_files, cleanup_exports_files
from app.core.config import settings, reload_config
from app.core.providers import PROVIDERS, get_available_models
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
            },
            "options": {
                "providers": providers_info
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
        env_path = os.path.join(os.getcwd(), ".env")
        if not os.path.exists(env_path):
             # Try looking one level up if not found (development mode often runs from backend dir)
            env_path_up = os.path.join(os.path.dirname(os.getcwd()), ".env")
            if os.path.exists(env_path_up):
                env_path = env_path_up
            elif os.path.exists(os.path.join(os.getcwd(), "backend", ".env")):
                 env_path = os.path.join(os.getcwd(), "backend", ".env")

        if not os.path.exists(env_path):
            raise HTTPException(status_code=404, detail=".env file not found")

        # 读取现有的 .env 内容
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        updated_keys = set()
        
        # 准备要更新的键值对
        updates = {}
        if config.agent_provider is not None: updates["AGENT_PROVIDER"] = config.agent_provider
        if config.agent_model is not None: updates["AGENT_MODEL"] = config.agent_model
        if config.agent_temperature is not None: updates["AGENT_TEMPERATURE"] = str(config.agent_temperature)
        if config.graph_provider is not None: updates["GRAPH_PROVIDER"] = config.graph_provider
        if config.graph_model is not None: updates["GRAPH_MODEL"] = config.graph_model
        if config.graph_temperature is not None: updates["GRAPH_TEMPERATURE"] = str(config.graph_temperature)

        # 更新现有行
        for line in lines:
            key = line.split("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        
        # 如果有新的键不在文件中，添加它们 (虽然在这个场景下应该都在，但为了健壮性)
        for key, value in updates.items():
            if key not in updated_keys:
                if new_lines and not new_lines[-1].endswith("\n"):
                    new_lines.append("\n")
                new_lines.append(f"{key}={value}\n")

        # 写入文件
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

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
