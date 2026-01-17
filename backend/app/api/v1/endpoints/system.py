from fastapi import APIRouter, HTTPException, Body
from app.utils.temp_file_manager import cleanup_all_temp_files, cleanup_exports_files

router = APIRouter()

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
