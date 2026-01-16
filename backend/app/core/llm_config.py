from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator


class LLMProvider(str, Enum):
    """LLM 供应商枚举"""
    MODELSCOPE = "modelscope"
    DEEPSEEK = "deepseek"
    AZURE = "azure"
    IFLOW = "iflow"
    OPENROUTER = "openrouter"
    CUSTOM = "custom"


class ProviderConfig(BaseModel):
    """供应商配置模型"""
    name: str
    base_url: str
    api_key_env: str
    agent_models: List[str] = Field(default_factory=list)
    graph_models: List[str] = Field(default_factory=list)


PROVIDER_CONFIGS: Dict[LLMProvider, ProviderConfig] = {
    LLMProvider.MODELSCOPE: ProviderConfig(
        name="ModelScope",
        base_url="https://api-inference.modelscope.cn/v1",
        api_key_env="MODELSCOPE_API_KEY",
        agent_models=[
            "Qwen/Qwen3-Next-80B-A3B-Instruct",
            "Qwen/Qwen3-235B-A22B-Instruct",
        ],
        graph_models=[
            "Qwen/Qwen3-VL-30B-A3B-Instruct",
            "Qwen/Qwen3-VL-235B-A22B-Instruct",
        ]
    ),
    LLMProvider.DEEPSEEK: ProviderConfig(
        name="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        api_key_env="DEEPSEEK_API_KEY",
        agent_models=[
            "deepseek-ai/DeepSeek-V3.2",
            "deepseek-ai/DeepSeek-V3.2-Exp",
            "deepseek-ai/DeepSeek-V2.5",
        ],
        graph_models=[
            "deepseek-ai/DeepSeek-V3.2",
            "deepseek-ai/DeepSeek-V2.5",
        ]
    ),
    LLMProvider.IFLOW: ProviderConfig(
        name="Iflow",
        base_url="https://apis.iflow.cn/v1",
        api_key_env="IFLOW_API_KEY",
        agent_models=[
            "qwen3-max",
            "qwen3-max-32k",
        ],
        graph_models=[
            "qwen3-max",
            "qwen3-max-32k",
        ]
    ),
    LLMProvider.OPENROUTER: ProviderConfig(
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        agent_models=[
            "anthropic/claude-haiku-4.5",
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5-mini",
            "openai/gpt-5.2",
            "google/gemini-3-flash-preview",
            "google/gemini-3-pro-preview",
            "qwen/qwen3-vl-235b-a22b-instruct",
            "qwen/qwen3-next-80b-a3b-instruct",
        ],
        graph_models=[
            "anthropic/claude-haiku-4.5",
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5-mini",
            "openai/gpt-5.2",
            "google/gemini-3-flash-preview",
            "google/gemini-3-pro-preview",
            "qwen/qwen3-vl-235b-a22b-instruct",
            "qwen/qwen3-next-80b-a3b-instruct",
        ]
    ),
    LLMProvider.CUSTOM: ProviderConfig(
        name="Custom",
        base_url="",
        api_key_env="CUSTOM_API_KEY",
        agent_models=[],
        graph_models=[]
    )
}


class LLMRoleConfig(BaseModel):
    """LLM 角色配置（agent 或 graph）"""
    provider: LLMProvider
    model: str
    temperature: float = 0.1
    api_key: str = ""
    base_url: str = ""
    
    @field_validator("provider", mode="before")
    @classmethod
    def parse_provider(cls, v):
        if isinstance(v, str):
            try:
                return LLMProvider(v.lower())
            except ValueError:
                return LLMProvider.CUSTOM
        return v


class LLMSettings(BaseModel):
    """LLM 配置设置"""
    agent: LLMRoleConfig
    graph: LLMRoleConfig
    
    def get_provider_info(self, provider: LLMProvider) -> ProviderConfig:
        """获取供应商信息"""
        return PROVIDER_CONFIGS.get(provider, PROVIDER_CONFIGS[LLMProvider.CUSTOM])
    
    def get_available_models(self, provider: LLMProvider, role: str = "agent") -> List[str]:
        """获取可用模型列表"""
        provider_config = self.get_provider_info(provider)
        if role == "agent":
            return provider_config.agent_models
        return provider_config.graph_models
    
    def get_all_providers(self) -> List[Dict[str, str]]:
        """获取所有可用供应商列表"""
        return [
            {"id": p.value, "name": cfg.name}
            for p, cfg in PROVIDER_CONFIGS.items()
        ]
