from typing import List, Dict, Any
from pydantic import AnyHttpUrl, field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_openai import ChatOpenAI

from app.core.providers import PROVIDERS, get_provider_config


class Settings(BaseSettings):
    """应用配置"""
    
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
    
    AGENT_PROVIDER: str = "modelscope"
    AGENT_MODEL: str = "Qwen/Qwen3-Next-80B-A3B-Instruct"
    AGENT_TEMPERATURE: float = 0.1
    
    GRAPH_PROVIDER: str = "modelscope"
    GRAPH_MODEL: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    GRAPH_TEMPERATURE: float = 0.1

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    def get_agent_config(self) -> Dict[str, Any]:
        """获取 Agent 配置（向后兼容）"""
        return {
            "provider": self.AGENT_PROVIDER,
            "name": self.AGENT_PROVIDER,
            "model": self.AGENT_MODEL,
            "temperature": self.AGENT_TEMPERATURE,
            "api_key": self._get_api_key(self.AGENT_PROVIDER),
            "base_url": self._get_base_url(self.AGENT_PROVIDER),
        }

    def get_graph_config(self) -> Dict[str, Any]:
        """获取 Graph 配置（向后兼容）"""
        return {
            "provider": self.GRAPH_PROVIDER,
            "name": self.GRAPH_PROVIDER,
            "model": self.GRAPH_MODEL,
            "temperature": self.GRAPH_TEMPERATURE,
            "api_key": self._get_api_key(self.GRAPH_PROVIDER),
            "base_url": self._get_base_url(self.GRAPH_PROVIDER),
        }

    def _get_api_key(self, provider: str) -> str:
        """根据供应商获取 API Key"""
        cfg = get_provider_config(provider)
        if not cfg:
            return ""
        return getattr(self, cfg["api_key_env"], "")

    def _get_base_url(self, provider: str) -> str:
        """根据供应商获取 Base URL"""
        cfg = get_provider_config(provider)
        if not cfg:
            return ""
        return cfg["base_url"]

    def get_all_providers(self):
        """获取所有供应商列表"""
        from app.core.providers import get_all_providers
        return get_all_providers()

    def get_available_models(self, provider: str, role: str = "agent"):
        """获取可用模型列表"""
        from app.core.providers import get_available_models
        return get_available_models(provider, role)

    def get_current_config(self) -> Dict[str, Any]:
        """获取当前完整配置（向后兼容）"""
        return {
            "agent": {
                "provider": self.AGENT_PROVIDER,
                "name": self.AGENT_PROVIDER,
                "model": self.AGENT_MODEL,
                "temperature": self.AGENT_TEMPERATURE,
            },
            "graph": {
                "provider": self.GRAPH_PROVIDER,
                "name": self.GRAPH_PROVIDER,
                "model": self.GRAPH_MODEL,
                "temperature": self.GRAPH_TEMPERATURE,
            },
            "available_providers": self.get_all_providers(),
            "agent_models": self.get_available_models(self.AGENT_PROVIDER, "agent"),
            "graph_models": self.get_available_models(self.GRAPH_PROVIDER, "graph"),
        }


settings = Settings()


def reload_config():
    global settings
    settings = Settings()


def create_llm_client(role: str = "agent") -> ChatOpenAI:
    """创建 LLM 客户端"""
    if role == "agent":
        provider = settings.AGENT_PROVIDER
        model = settings.AGENT_MODEL
        temperature = settings.AGENT_TEMPERATURE
    else:
        provider = settings.GRAPH_PROVIDER
        model = settings.GRAPH_MODEL
        temperature = settings.GRAPH_TEMPERATURE

    cfg = get_provider_config(provider)
    if not cfg:
        raise ValueError(f"Unknown provider: {provider}")

    api_key = getattr(settings, cfg["api_key_env"], "")
    if not api_key:
        raise ValueError(f"API Key not found for provider {provider}. Please set {cfg['api_key_env']} in .env file")

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
        base_url=cfg["base_url"],
    )


__all__ = ["settings", "reload_config", "create_llm_client"]
