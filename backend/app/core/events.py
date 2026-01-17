from typing import Callable
from fastapi import FastAPI
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_env_observer = None

class EnvFileHandler:
    def __init__(self, reload_callback):
        self.reload_callback = reload_callback
        self.last_modified = 0

    def check_and_reload(self):
        env_path = Path(".env")
        if not env_path.exists():
            return

        current_modified = env_path.stat().st_mtime
        if current_modified != self.last_modified and self.last_modified > 0:
            logger.info("检测到 .env 文件变化，重新加载配置...")
            try:
                self.reload_callback()
                logger.info("配置重新加载成功")
            except Exception as e:
                logger.error(f"配置重新加载失败: {e}")
            finally:
                self.last_modified = current_modified

    def initialize(self):
        env_path = Path(".env")
        if env_path.exists():
            self.last_modified = env_path.stat().st_mtime

def create_start_app_handler(app: FastAPI) -> Callable:
    def start_app() -> None:
        from app.core.config import reload_config
        
        global _env_observer
        _env_observer = EnvFileHandler(reload_callback=reload_config)
        _env_observer.initialize()
        
        logger.info("Application starting up...")
        logger.info("配置文件监听已启动（修改 .env 后自动生效）")
    return start_app

def create_stop_app_handler(app: FastAPI) -> Callable:
    def stop_app() -> None:
        global _env_observer
        _env_observer = None
        logger.info("Application shutting down...")
    return stop_app

def check_env_changes():
    if _env_observer:
        _env_observer.check_and_reload()
