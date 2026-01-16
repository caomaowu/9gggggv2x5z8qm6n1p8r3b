from typing import Optional
from langchain_openai import ChatOpenAI

from app.core.llm_config import LLMSettings, LLMProvider, PROVIDER_CONFIGS, LLMRoleConfig
from app.core.app_settings import AppSettings


def create_llm_client(
    settings: AppSettings,
    llm_config: LLMSettings,
    role: str = "agent",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> ChatOpenAI:
    """
    创建 LLM 客户端的工厂函数
    
    Args:
        settings: 应用设置
        llm_config: LLM 配置
        role: 角色类型 "agent" 或 "graph"
        provider: 供应商名称（可选，覆盖配置）
        model: 模型名称（可选，覆盖配置）
        temperature: 温度参数（可选，覆盖配置）
    
    Returns:
        ChatOpenAI 实例
    
    Example:
        from app.core.app_settings import app_settings
        from app.core.llm_settings import llm_settings
        
        agent_llm = create_llm_client(app_settings, llm_settings, role="agent")
        graph_llm = create_llm_client(app_settings, llm_settings, role="graph")
    """
    role_config = llm_config.agent if role == "agent" else llm_config.graph
    
    if provider:
        provider_enum = _parse_provider(provider)
        provider_cfg = PROVIDER_CONFIGS[provider_enum]
        actual_model = model or provider_cfg.agent_models[0] if role == "agent" else provider_cfg.graph_models[0]
        actual_temp = temperature if temperature is not None else 0.1
        
        api_key = getattr(settings, provider_cfg.api_key_env, "")
        if not api_key:
            raise ValueError(f"API Key not found for provider {provider}. Please set {provider_cfg.api_key_env} in .env file")
        
        return ChatOpenAI(
            model=actual_model,
            temperature=actual_temp,
            api_key=api_key,
            base_url=provider_cfg.base_url,
        )
    
    return ChatOpenAI(
        model=model or role_config.model,
        temperature=temperature if temperature is not None else role_config.temperature,
        api_key=role_config.api_key,
        base_url=role_config.base_url,
    )


def _parse_provider(provider: str) -> LLMProvider:
    """解析供应商字符串为枚举"""
    try:
        return LLMProvider(provider.lower())
    except ValueError:
        return LLMProvider.CUSTOM
