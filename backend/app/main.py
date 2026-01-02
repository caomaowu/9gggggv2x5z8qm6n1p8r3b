from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from app.core.config import settings
from app.core.events import create_start_app_handler, create_stop_app_handler
from app.api.v1.api import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 允许所有源，解决开发环境跨域问题
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_event_handler("startup", create_start_app_handler(app))
app.add_event_handler("shutdown", create_stop_app_handler(app))

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
def root():
    return {"message": "Welcome to QuantAgent API", "version": "2.0"}
