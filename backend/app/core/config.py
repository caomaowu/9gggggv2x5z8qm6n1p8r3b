from typing import List, Union, Dict, Any, Optional
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dataclasses import dataclass, field
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "QuantAgent"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Market Data API
    MARKET_DATA_API_URL: str = "https://caomao.xyz"
    MARKET_DATA_API_TOKEN: str = "api-header-I1iMwyAmXC4H6c58_O9kPjk1BxytE9RQlLgN--SohbY"
    
    # LLM
    OPENAI_API_KEY: str = "ms-5b276203-2e1d-4083-b7e8-113630a13a14"
    OPENAI_API_BASE: str = "https://api-inference.modelscope.cn/v1"
    AGENT_MODEL: str = "Qwen/Qwen3-Next-80B-A3B-Instruct"
    GRAPH_MODEL: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()

# --- Legacy Config Support for Ported Modules ---

@dataclass
class LLMConfig:
    agent_model: str = settings.AGENT_MODEL
    graph_model: str = settings.GRAPH_MODEL
    agent_temperature: float = 0.1
    graph_temperature: float = 0.1
    api_key: str = settings.OPENAI_API_KEY
    base_url: str = settings.OPENAI_API_BASE
    
    # Dual model support
    dual_model_enabled: bool = False
    agent_model_2: str = "deepseek-ai/DeepSeek-V3.2-Exp"
    agent_temperature_2: float = 0.1

@dataclass
class APIConfig:
    quant_base_url: str = settings.MARKET_DATA_API_URL
    quant_token: str = settings.MARKET_DATA_API_TOKEN
    timeout: int = 15
    max_retries: int = 2

# Singleton instance for legacy code
config = None # Will be initialized if needed, or we can mock it.

class Config:
    def __init__(self):
        self.llm = LLMConfig()
        self.api = APIConfig()
    
    def get(self, key, default=None):
        # Helper to mimic dictionary-like access if needed
        return default

# Create a global config instance that mimics the old behavior
config = Config()
