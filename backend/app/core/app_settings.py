from typing import List
from pydantic import AnyHttpUrl, field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    """应用核心配置"""
    
    PROJECT_NAME: str = "QuantAgent"
    API_V1_STR: str = "/api/v1"
    
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    MARKET_DATA_API_URL: str = "https://caomao.xyz"
    MARKET_DATA_API_TOKEN: SecretStr = SecretStr("")
    
    MODELSCOPE_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    IFLOW_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    CUSTOM_API_KEY: str = ""
    CUSTOM_API_BASE: str = ""
    CUSTOM_AGENT_MODEL: str = ""
    CUSTOM_GRAPH_MODEL: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


app_settings = AppSettings()
