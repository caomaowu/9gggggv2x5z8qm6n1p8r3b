from typing import Callable
from fastapi import FastAPI
import logging

logger = logging.getLogger(__name__)

def create_start_app_handler(app: FastAPI) -> Callable:
    def start_app() -> None:
        # Code to execute on startup
        logger.info("Application starting up...")
    return start_app

def create_stop_app_handler(app: FastAPI) -> Callable:
    def stop_app() -> None:
        # Code to execute on shutdown
        logger.info("Application shutting down...")
    return stop_app
