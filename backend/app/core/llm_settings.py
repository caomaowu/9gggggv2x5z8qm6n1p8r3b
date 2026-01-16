import os
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from app.core.llm_config import LLMProvider, LLMRoleConfig, LLMSettings, PROVIDER_CONFIGS
from app.core.app_settings import AppSettings
from app.core.config_repository import global_config_repository


class LLMConfigManager(BaseModel):
    """LLM 配置管理器 - 统一的配置访问接口"""
    
    app_settings: AppSettings
    llm_settings: LLMSettings
    
    class Config:
        arbitrary_types_allowed = True
    
    @classmethod
    def load(cls) -> "LLMConfigManager":
        """从环境变量加载配置"""
        app_settings = AppSettings()
        
        agent_config = _load_role_config(
            app_settings, 
            provider_env="AGENT_PROVIDER",
            model_env="AGENT_MODEL",
            temp_env="AGENT_TEMPERATURE",
            default_provider="modelscope",
            default_model="Qwen/Qwen3-Next-80B-A3B-Instruct"
        )
        
        graph_config = _load_role_config(
            app_settings,
            provider_env="GRAPH_PROVIDER",
            model_env="GRAPH_MODEL",
            temp_env="GRAPH_TEMPERATURE",
            default_provider="modelscope",
            default_model="Qwen/Qwen3-VL-30B-A3B-Instruct"
        )
        
        llm_settings = LLMSettings(agent=agent_config, graph=graph_config)
        
        return cls(app_settings=app_settings, llm_settings=llm_settings)
    
    def get_agent_config(self) -> LLMRoleConfig:
        """获取 Agent 配置"""
        return self.llm_settings.agent
    
    def get_graph_config(self) -> LLMRoleConfig:
        """获取 Graph 配置"""
        return self.llm_settings.graph
    
    def get_agent_provider_config(self) -> Dict[str, Any]:
        """获取 Agent 配置（兼容旧接口）"""
        cfg = self.llm_settings.agent
        return {
            "provider": cfg.provider.value,
            "name": cfg.provider.value,
            "model": cfg.model,
            "temperature": cfg.temperature,
            "api_key": cfg.api_key,
            "base_url": cfg.base_url
        }
    
    def get_graph_provider_config(self) -> Dict[str, Any]:
        """获取 Graph 配置（兼容旧接口）"""
        cfg = self.llm_settings.graph
        return {
            "provider": cfg.provider.value,
            "name": cfg.provider.value,
            "model": cfg.model,
            "temperature": cfg.temperature,
            "api_key": cfg.api_key,
            "base_url": cfg.base_url
        }
    
    def get_all_providers(self) -> List[Dict[str, str]]:
        """获取所有可用供应商列表"""
        return self.llm_settings.get_all_providers()
    
    def get_available_models(self, provider: str, role: str = "agent") -> List[str]:
        """获取可用模型列表"""
        provider_enum = _parse_provider(provider)
        return self.llm_settings.get_available_models(provider_enum, role)
    
    def set_agent_provider(self, provider: str, model: Optional[str] = None, 
                           temperature: Optional[float] = None, persist: bool = False) -> None:
        """
        设置 Agent 配置
        
        Args:
            provider: 供应商名称
            model: 模型名称（可选）
            temperature: 温度参数（可选）
            persist: 是否持久化到 .env 文件
        """
        updates = {"AGENT_PROVIDER": provider}
        if model:
            updates["AGENT_MODEL"] = model
        if temperature is not None:
            updates["AGENT_TEMPERATURE"] = str(temperature)
        
        if persist:
            global_config_repository.update_env_file(updates)
        
        self.llm_settings.agent = _load_role_config(
            self.app_settings,
            provider_env="AGENT_PROVIDER",
            model_env="AGENT_MODEL",
            temp_env="AGENT_TEMPERATURE",
            default_provider=provider,
            default_model=model or "Qwen/Qwen3-Next-80B-A3B-Instruct"
        )
    
    def set_graph_provider(self, provider: str, model: Optional[str] = None,
                           temperature: Optional[float] = None, persist: bool = False) -> None:
        """
        设置 Graph 配置
        
        Args:
            provider: 供应商名称
            model: 模型名称（可选）
            temperature: 温度参数（可选）
            persist: 是否持久化到 .env 文件
        """
        updates = {"GRAPH_PROVIDER": provider}
        if model:
            updates["GRAPH_MODEL"] = model
        if temperature is not None:
            updates["GRAPH_TEMPERATURE"] = str(temperature)
        
        if persist:
            global_config_repository.update_env_file(updates)
        
        self.llm_settings.graph = _load_role_config(
            self.app_settings,
            provider_env="GRAPH_PROVIDER",
            model_env="GRAPH_MODEL",
            temp_env="GRAPH_TEMPERATURE",
            default_provider=provider,
            default_model=model or "Qwen/Qwen3-VL-30B-A3B-Instruct"
        )
    
    def get_current_config(self) -> Dict[str, Any]:
        """获取当前完整配置"""
        return {
            "agent": {
                "provider": self.llm_settings.agent.provider.value,
                "name": self.llm_settings.agent.provider.value,
                "model": self.llm_settings.agent.model,
                "temperature": self.llm_settings.agent.temperature,
            },
            "graph": {
                "provider": self.llm_settings.graph.provider.value,
                "name": self.llm_settings.graph.provider.value,
                "model": self.llm_settings.graph.model,
                "temperature": self.llm_settings.graph.temperature,
            },
            "available_providers": self.get_all_providers(),
            "agent_models": self.get_available_models(self.llm_settings.agent.provider.value, "agent"),
            "graph_models": self.get_available_models(self.llm_settings.graph.provider.value, "graph"),
        }
    
    def reload(self) -> None:
        """重新加载配置"""
        new_config = self.load()
        self.app_settings = new_config.app_settings
        self.llm_settings = new_config.llm_settings


def _load_role_config(
    app_settings: AppSettings,
    provider_env: str,
    model_env: str,
    temp_env: str,
    default_provider: str,
    default_model: str
) -> LLMRoleConfig:
    """加载角色配置"""
    provider_str = os.getenv(provider_env, default_provider)
    provider_enum = _parse_provider(provider_str)
    
    if provider_enum == LLMProvider.CUSTOM:
        custom_api_key = os.getenv("CUSTOM_API_KEY", "")
        custom_base_url = os.getenv("CUSTOM_API_BASE", "")
        custom_agent_model = os.getenv("CUSTOM_AGENT_MODEL", "")
        custom_graph_model = os.getenv("CUSTOM_GRAPH_MODEL", "")
        
        return LLMRoleConfig(
            provider=provider_enum,
            model=custom_agent_model if provider_env == "AGENT_PROVIDER" else custom_graph_model,
            temperature=float(os.getenv(temp_env, "0.1")),
            api_key=custom_api_key or app_settings.MODELSCOPE_API_KEY,
            base_url=custom_base_url or "https://custom-api.example.com/v1"
        )
    
    provider_cfg = PROVIDER_CONFIGS[provider_enum]
    model = os.getenv(model_env, default_model)
    temperature = float(os.getenv(temp_env, "0.1"))
    
    api_key = ""
    if provider_cfg.api_key_env == "MODELSCOPE_API_KEY":
        api_key = app_settings.MODELSCOPE_API_KEY
    elif provider_cfg.api_key_env == "DEEPSEEK_API_KEY":
        api_key = app_settings.DEEPSEEK_API_KEY
    elif provider_cfg.api_key_env == "IFLOW_API_KEY":
        api_key = app_settings.IFLOW_API_KEY
    elif provider_cfg.api_key_env == "OPENROUTER_API_KEY":
        api_key = app_settings.OPENROUTER_API_KEY
    elif provider_cfg.api_key_env == "CUSTOM_API_KEY":
        api_key = app_settings.CUSTOM_API_KEY
    
    return LLMRoleConfig(
        provider=provider_enum,
        model=model,
        temperature=temperature,
        api_key=api_key,
        base_url=provider_cfg.base_url
    )


def _parse_provider(provider: str) -> LLMProvider:
    """解析供应商字符串为枚举"""
    try:
        return LLMProvider(provider.lower())
    except ValueError:
        return LLMProvider.CUSTOM


global_llm_config_manager = LLMConfigManager.load()
