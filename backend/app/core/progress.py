import logging
import asyncio

logger = logging.getLogger(__name__)

# Simple in-memory progress tracker for now
progress_store = {}

def update_agent_progress(agent_name: str, progress_within_agent: int = 0, status: str = "", session_id: str = "default"):
    """
    Update progress for a specific agent.
    """
    logger.info(f"[Progress] {agent_name}: {progress_within_agent}% - {status}")
    
    # Broadcast via WebSocket
    try:
        from app.api.v1.endpoints.ws import manager
        msg = {
            "type": "agent_progress",
            "agent": agent_name,
            "progress": progress_within_agent,
            "status": status,
            "session_id": session_id
        }
        # Since this might be called from sync code, we need to handle async
        # For now, just fire and forget if possible, or use a background task approach if in FastAPI context
        # But here we are deep in logic. 
        # Ideally, we should use an async event loop or a queue.
        # For simplicity in this refactor, we might skip actual async send if running synchronously.
        # But let's try to get the running loop.
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast(msg))
        except RuntimeError:
            pass # No loop running
            
    except ImportError:
        pass

def update_analysis_progress(stage: str, progress: int, status: str, session_id: str = "default"):
    """
    Update overall analysis progress.
    """
    logger.info(f"[Analysis Progress] {stage}: {progress}% - {status}")
    
    try:
        from app.api.v1.endpoints.ws import manager
        msg = {
            "type": "analysis_progress",
            "stage": stage,
            "progress": progress,
            "status": status,
            "session_id": session_id
        }
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(manager.broadcast(msg))
        except RuntimeError:
            pass
    except ImportError:
        pass
