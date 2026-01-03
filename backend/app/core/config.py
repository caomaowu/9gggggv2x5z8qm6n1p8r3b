from typing import List, Union, Dict, Any, Optional
from pydantic import AnyHttpUrl, field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dataclasses import dataclass, field
from enum import Enum
import os


class LLMProvider(str, Enum):
    """LLM 供应商枚举"""
    MODELSCOPE = "modelscope"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    IFLOW = "iflow"
    CUSTOM = "custom"


# --- 供应商模型映射 ---
PROVIDER_MODELS: Dict[LLMProvider, Dict[str, Any]] = {
    LLMProvider.MODELSCOPE: {
        "name": "ModelScope",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key_env": "MODELSCOPE_API_KEY",
        "models": {
            "agent": [
                "Qwen/Qwen3-Next-80B-A3B-Instruct",
                "Qwen/Qwen3-235B-A22B-Instruct",
            ],
            "graph": [
                "Qwen/Qwen3-VL-30B-A3B-Instruct",
                "Qwen/Qwen3-VL-235B-A22B-Instruct",
            ]
        }
    },
    LLMProvider.OPENAI: {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key_env": "OPENAI_API_KEY",
        "models": {
            "agent": [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
            ],
            "graph": [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-vision-preview",
            ]
        }
    },
    LLMProvider.DEEPSEEK: {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "models": {
            "agent": [
                "deepseek-ai/DeepSeek-V3.2",
                "deepseek-ai/DeepSeek-V3.2-Exp",
                "deepseek-ai/DeepSeek-V2.5",
            ],
            "graph": [
                "deepseek-ai/DeepSeek-V3.2",
                "deepseek-ai/DeepSeek-V2.5",
            ]
        }
    },
    LLMProvider.ANTHROPIC: {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key_env": "ANTHROPIC_API_KEY",
        "models": {
            "agent": [
                "claude-sonnet-4-20250514",
                "claude-opus-4-20250514",
                "claude-haiku-3-20250514",
            ],
            "graph": [
                "claude-sonnet-4-20250514",
                "claude-opus-4-20250514",
            ]
        }
    },
    LLMProvider.IFLOW: {
        "name": "Iflow",
        "base_url": "https://apis.iflow.cn/v1",
        "api_key_env": "IFLOW_API_KEY",
        "models": {
            "agent": [
                "qwen3-max",
                "qwen3-max-32k",
            ],
            "graph": [
                "qwen3-max",
                "qwen3-max-32k",
            ]
        }
    },
    LLMProvider.CUSTOM: {
        "name": "Custom",
        "base_url": "",  # 必须在 .env 中配置
        "api_key_env": "CUSTOM_API_KEY",
        "models": {
            "agent": [],
            "graph": []
        }
    }
}


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
    
    # --- 新版 LLM 配置 ---
    
    # Agent LLM 配置
    AGENT_PROVIDER: str = "modelscope"  # 供应商名称
    AGENT_MODEL: str = "Qwen/Qwen3-Next-80B-A3B-Instruct"
    AGENT_TEMPERATURE: float = 0.1
    
    # Graph LLM 配置
    GRAPH_PROVIDER: str = "modelscope"
    GRAPH_MODEL: str = "Qwen/Qwen3-VL-30B-A3B-Instruct"
    GRAPH_TEMPERATURE: float = 0.1
    
    # API Keys（按供应商存储）
    MODELSCOPE_API_KEY: str = "ms-5b276203-2e1d-4083-b7e8-113630a13a14"
    OPENAI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    IFLOW_API_KEY: str = ""
    CUSTOM_API_KEY: str = ""
    
    # 自定义 API 端点（用于 custom 供应商）
    CUSTOM_API_BASE: str = ""
    CUSTOM_AGENT_MODEL: str = ""
    CUSTOM_GRAPH_MODEL: str = ""
    
    # 共享配置（向后兼容）
    LEGACY_OPENAI_API_KEY: str = ""  # 旧配置，优先使用供应商专用 key
    LEGACY_OPENAI_API_BASE: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    def get_agent_provider_config(self) -> Dict[str, Any]:
        """获取 Agent LLM 的完整配置"""
        provider_name = self.AGENT_PROVIDER.lower()
        try:
            provider = LLMProvider(provider_name)
        except ValueError:
            provider = LLMProvider.CUSTOM
        
        if provider == LLMProvider.CUSTOM:
            return {
                "provider": provider,
                "name": "Custom",
                "model": self.CUSTOM_AGENT_MODEL or self.AGENT_MODEL,
                "temperature": self.AGENT_TEMPERATURE,
                "api_key": self.CUSTOM_API_KEY or self.MODELSCOPE_API_KEY,  # fallback
                "base_url": self.CUSTOM_API_BASE or "https://custom-api.example.com/v1"
            }
        
        provider_info = PROVIDER_MODELS[provider]
        api_key = getattr(self, provider_info["api_key_env"], "")
        
        return {
            "provider": provider,
            "name": provider_info["name"],
            "model": self.AGENT_MODEL,
            "temperature": self.AGENT_TEMPERATURE,
            "api_key": api_key,
            "base_url": provider_info["base_url"]
        }
    
    def get_graph_provider_config(self) -> Dict[str, Any]:
        """获取 Graph LLM 的完整配置"""
        provider_name = self.GRAPH_PROVIDER.lower()
        try:
            provider = LLMProvider(provider_name)
        except ValueError:
            provider = LLMProvider.CUSTOM
        
        if provider == LLMProvider.CUSTOM:
            return {
                "provider": provider,
                "name": "Custom",
                "model": self.CUSTOM_GRAPH_MODEL or self.GRAPH_MODEL,
                "temperature": self.GRAPH_TEMPERATURE,
                "api_key": self.CUSTOM_API_KEY or self.MODELSCOPE_API_KEY,
                "base_url": self.CUSTOM_API_BASE or "https://custom-api.example.com/v1"
            }
        
        provider_info = PROVIDER_MODELS[provider]
        api_key = getattr(self, provider_info["api_key_env"], "")
        
        return {
            "provider": provider,
            "name": provider_info["name"],
            "model": self.GRAPH_MODEL,
            "temperature": self.GRAPH_TEMPERATURE,
            "api_key": api_key,
            "base_url": provider_info["base_url"]
        }
    
    def get_available_models(self, provider: str = None, role: str = "agent") -> List[str]:
        """获取可用模型列表"""
        if provider is None:
            provider = self.AGENT_PROVIDER if role == "agent" else self.GRAPH_PROVIDER
        
        provider_name = provider.lower()
        try:
            provider_enum = LLMProvider(provider_name)
        except ValueError:
            provider_enum = LLMProvider.CUSTOM
        
        if provider_enum == LLMProvider.CUSTOM:
            # Custom 供应商返回手动配置的模型
            if role == "agent":
                return [self.CUSTOM_AGENT_MODEL] if self.CUSTOM_AGENT_MODEL else []
            else:
                return [self.CUSTOM_GRAPH_MODEL] if self.CUSTOM_GRAPH_MODEL else []
        
        return PROVIDER_MODELS[provider_enum].get("models", {}).get(role, [])
    
    def get_all_providers(self) -> List[Dict[str, str]]:
        """获取所有可用供应商列表"""
        return [
            {"id": p.value, "name": info["name"]}
            for p, info in PROVIDER_MODELS.items()
        ]


settings = Settings()

# --- 新版 LLM 工厂函数（推荐使用）---

def create_llm_client(
    provider: str = None, 
    model: str = None, 
    temperature: float = None,
    role: str = "agent"  # "agent" or "graph"
):
    """
    创建 LLM 客户端的工厂函数
    
    Args:
        provider: 供应商名称 (modelscope, openai, deepseek, anthropic, custom)
        model: 模型名称，如果为 None 则使用配置中的默认模型
        temperature: 温度参数，如果为 None 则使用配置中的默认温度
        role: 角色类型，"agent" 或 "graph"
    
    Returns:
        ChatOpenAI 实例
    
    Example:
        # 使用当前配置创建 Agent LLM
        agent_llm = create_llm_client(role="agent")
        
        # 使用 DeepSeek 创建 Agent LLM
        agent_llm = create_llm_client(provider="deepseek", model="deepseek-ai/DeepSeek-V3.2")
        
        # 使用自定义配置创建 Graph LLM
        graph_llm = create_llm_client(role="graph", temperature=0.2)
    """
    from langchain_openai import ChatOpenAI
    
    if role == "agent":
        provider_config = settings.get_agent_provider_config()
    else:
        provider_config = settings.get_graph_provider_config()
    
    # 覆盖配置
    if provider:
        # 临时切换供应商
        original_provider = settings.AGENT_PROVIDER if role == "agent" else settings.GRAPH_PROVIDER
        if role == "agent":
            settings.AGENT_PROVIDER = provider
            provider_config = settings.get_agent_provider_config()
            settings.AGENT_PROVIDER = original_provider  # 恢复
        else:
            settings.GRAPH_PROVIDER = provider
            provider_config = settings.get_graph_provider_config()
            settings.GRAPH_PROVIDER = original_provider  # 恢复
    
    actual_model = model or provider_config["model"]
    actual_temperature = temperature if temperature is not None else provider_config["temperature"]
    
    return ChatOpenAI(
        model=actual_model,
        temperature=actual_temperature,
        api_key=provider_config["api_key"],
        base_url=provider_config["base_url"],
    )


def get_llm_info(provider: str = None, role: str = "agent") -> Dict[str, Any]:
    """
    获取 LLM 配置信息的便捷函数
    
    Returns:
        包含配置信息的字典
    """
    if role == "agent":
        return settings.get_agent_provider_config()
    else:
        return settings.get_graph_provider_config()


# --- Legacy Config Support for Ported Modules ---

@dataclass
class LLMConfig:
    """向后兼容的 LLM 配置类 - 现在使用供应商配置"""
    
    def __init__(self):
        # 从新版配置获取
        agent_config = settings.get_agent_provider_config()
        graph_config = settings.get_graph_provider_config()
        
        self.agent_model: str = agent_config["model"]
        self.graph_model: str = graph_config["model"]
        self.agent_temperature: float = agent_config["temperature"]
        self.graph_temperature: float = graph_config["temperature"]
        self.api_key: str = agent_config["api_key"]
        self.base_url: str = agent_config["base_url"]
        
        # Dual model support
        self.dual_model_enabled: bool = False
        self.agent_model_2: str = "deepseek-ai/DeepSeek-V3.2-Exp"
        self.agent_temperature_2: float = 0.1
    
    def update_from_provider_config(self):
        """从供应商配置更新"""
        agent_config = settings.get_agent_provider_config()
        graph_config = settings.get_graph_provider_config()
        
        self.agent_model = agent_config["model"]
        self.graph_model = graph_config["model"]
        self.agent_temperature = agent_config["temperature"]
        self.graph_temperature = graph_config["temperature"]
        self.api_key = agent_config["api_key"]
        self.base_url = agent_config["base_url"]

@dataclass
class APIConfig:
    quant_base_url: str = settings.MARKET_DATA_API_URL
    quant_token: str = settings.MARKET_DATA_API_TOKEN
    timeout: int = 15
    max_retries: int = 2

class Config:
    """
    全局配置类 - 向后兼容
    提供 config.llm 和 config.api 访问方式
    """
    
    def __init__(self):
        self._llm_config = None
        self._api_config = None
    
    @property
    def llm(self) -> LLMConfig:
        """获取 LLM 配置（懒加载）"""
        if self._llm_config is None:
            self._llm_config = LLMConfig()
        return self._llm_config
    
    @property
    def api(self) -> APIConfig:
        """获取 API 配置（懒加载）"""
        if self._api_config is None:
            self._api_config = APIConfig()
        return self._api_config
    
    def reload_llm_config(self):
        """重新加载 LLM 配置"""
        self._llm_config = LLMConfig()
    
    def set_agent_provider(self, provider: str, model: str = None):
        """
        设置 Agent LLM 供应商和模型
        
        Args:
            provider: 供应商名称
            model: 可选的模型名称
        """
        settings.AGENT_PROVIDER = provider
        if model:
            settings.AGENT_MODEL = model
        self.reload_llm_config()
    
    def set_graph_provider(self, provider: str, model: str = None):
        """
        设置 Graph LLM 供应商和模型
        
        Args:
            provider: 供应商名称
            model: 可选的模型名称
        """
        settings.GRAPH_PROVIDER = provider
        if model:
            settings.GRAPH_MODEL = model
        self.reload_llm_config()
    
    def get_current_config(self) -> Dict[str, Any]:
        """获取当前完整配置"""
        return {
            "agent": settings.get_agent_provider_config(),
            "graph": settings.get_graph_provider_config(),
            "available_providers": settings.get_all_providers(),
            "agent_models": settings.get_available_models(role="agent"),
            "graph_models": settings.get_available_models(role="graph"),
        }

# 全局配置实例
config = Config()
