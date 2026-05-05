import logging
from typing import List, Dict, Any
from pydantic import AnyHttpUrl, field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_openai import ChatOpenAI

from app.core.providers import PROVIDERS, get_provider_config

logger = logging.getLogger(__name__)


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

    MARKET_DATA_API_URL: str = "https://webui.caomaowu.lol"
    MARKET_DATA_API_TOKEN: SecretStr = SecretStr("")
    
    MODELSCOPE_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    IFLOW_API_KEY: str = ""
    IFLOW2_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    ARK_API_KEY: str = ""
    CODEX_API_KEY: str = ""
    SOUL_API_KEY: str = ""
    API302_API_KEY: str = ""
    
    AGENT_PROVIDER: str = "modelscope"
    AGENT_MODEL: str = "Qwen/Qwen3-Next-80B-A3B-Instruct"
    AGENT_TEMPERATURE: float = 0.1
    
    GRAPH_PROVIDER: str = "modelscope"
    GRAPH_MODEL: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    GRAPH_TEMPERATURE: float = 0.1
    
    OPTIMIZER_PROVIDER: str = "openrouter"
    OPTIMIZER_MODEL: str = "openai/gpt-4o"
    OPTIMIZER_TEMPERATURE: float = 0.7
    OPTIMIZER_API_KEY: str = ""

    # LLM Request Timeout (seconds)
    # 默认增加到 5 分钟 (300s) 以适应慢速推理模型
    LLM_TIMEOUT: float = 300.0

    # 思考模式独立开关
    INDICATOR_THINKING_MODE: bool = False
    PATTERN_THINKING_MODE: bool = False
    TREND_THINKING_MODE: bool = False
    DECISION_THINKING_MODE: bool = False

    # 思考模式推理深度 (low, medium, high, extra_high)
    # 默认为 medium
    INDICATOR_REASONING_EFFORT: str = "medium"
    PATTERN_REASONING_EFFORT: str = "medium"
    TREND_REASONING_EFFORT: str = "medium"
    DECISION_REASONING_EFFORT: str = "medium"

    # Decision Agent Version (original / lite)
    DECISION_AGENT_VERSION: str = "lite"

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
            "optimizer": {
                "provider": self.OPTIMIZER_PROVIDER,
                "name": self.OPTIMIZER_PROVIDER,
                "model": self.OPTIMIZER_MODEL,
                "temperature": self.OPTIMIZER_TEMPERATURE,
            },
            "available_providers": self.get_all_providers(),
            "agent_models": self.get_available_models(self.AGENT_PROVIDER, "agent"),
            "graph_models": self.get_available_models(self.GRAPH_PROVIDER, "graph"),
        }


settings = Settings()


def reload_config():
    global settings
    settings = Settings()


def create_llm_client(role: str = "agent", agent_name: str = None) -> ChatOpenAI:
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

    model_kwargs = {}
    
    # 判断是否开启思考模式
    enable_thinking = False
    reasoning_effort = "medium"
    
    if agent_name:
        if agent_name == "indicator":
            enable_thinking = settings.INDICATOR_THINKING_MODE
            reasoning_effort = settings.INDICATOR_REASONING_EFFORT
        elif agent_name == "pattern":
            enable_thinking = settings.PATTERN_THINKING_MODE
            reasoning_effort = settings.PATTERN_REASONING_EFFORT
        elif agent_name == "trend":
            enable_thinking = settings.TREND_THINKING_MODE
            reasoning_effort = settings.TREND_REASONING_EFFORT
        elif agent_name == "decision":
            enable_thinking = settings.DECISION_THINKING_MODE
            reasoning_effort = settings.DECISION_REASONING_EFFORT
    
    # 针对 OpenAI o1/o3/gpt-5 等推理模型处理
    # 如果开启思考模式且模型名称包含推理模型特征
    is_reasoning_model = model.startswith(("o1", "o3", "gpt-o1", "gpt-o3", "gpt-5"))
    
    if enable_thinking:
        logger.info(f"🧠 Thinking Mode Enabled for Agent: {agent_name} | Model: {model}")
        
        if provider == "openrouter":
            # OpenRouter 思考模式参数
            logger.info(f"Injecting OpenRouter reasoning params (extra_body)")
            model_kwargs["extra_body"] = {"reasoning": {"enabled": True}}
        elif is_reasoning_model:
            # OpenAI 原生推理模型参数
            logger.info(f"Injecting OpenAI reasoning params: effort={reasoning_effort}")
            model_kwargs["reasoning_effort"] = reasoning_effort
        else:
            logger.warning(f"Thinking Mode enabled but no specific params injected for provider {provider} and model {model}. Standard behavior applies.")
            
    # 构建基础参数
    client_kwargs = {
        "model": model,
        "api_key": api_key,
        "base_url": cfg["base_url"],
        "model_kwargs": model_kwargs,
        # 显式设置超时时间
        "request_timeout": settings.LLM_TIMEOUT,
        # 增加最大重试次数
        "max_retries": 3,
        # 关闭流式传输
        "streaming": False,
    }

    # 仅在非推理模型或明确需要 temperature 时才传入
    # 对于 o1/o3 模型，我们显式不传 temperature
    if not (enable_thinking and is_reasoning_model):
        client_kwargs["temperature"] = temperature

    return ChatOpenAI(**client_kwargs)


def create_optimizer_llm() -> ChatOpenAI:
    """创建 Optimizer 专用的 LLM 客户端"""
    provider = settings.OPTIMIZER_PROVIDER
    model = settings.OPTIMIZER_MODEL
    temperature = settings.OPTIMIZER_TEMPERATURE

    cfg = get_provider_config(provider)
    if not cfg:
        raise ValueError(f"Unknown provider: {provider}")

    # 优先使用 OPTIMIZER_API_KEY，如果没有则复用现有的 provider api key
    api_key = settings.OPTIMIZER_API_KEY or getattr(settings, cfg["api_key_env"], "")
    if not api_key:
        raise ValueError(f"API Key not found for optimizer provider {provider}. Please set OPTIMIZER_API_KEY or {cfg['api_key_env']} in .env file")

    client_kwargs = {
        "model": model,
        "api_key": api_key,
        "base_url": cfg["base_url"],
        "request_timeout": settings.LLM_TIMEOUT,
        "max_retries": 3,
        "streaming": False,
        "temperature": temperature,
    }

    return ChatOpenAI(**client_kwargs)


__all__ = ["settings", "reload_config", "create_llm_client", "create_optimizer_llm"]
