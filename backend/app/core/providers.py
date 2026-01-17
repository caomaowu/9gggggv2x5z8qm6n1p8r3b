"""预定义的 LLM 供应商和模型列表"""

PROVIDERS = {
    "modelscope": {
        "name": "ModelScope",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key_env": "MODELSCOPE_API_KEY",
        "agent_models": [
            "Qwen/Qwen3-Next-80B-A3B-Instruct",
            "Qwen/Qwen3-235B-A22B-Instruct",
        ],
        "graph_models": [
            "Qwen/Qwen3-VL-30B-A3B-Instruct",
            "Qwen/Qwen3-VL-235B-A22B-Instruct",
        ],
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "agent_models": [
            "deepseek-ai/DeepSeek-V3.2",
            "deepseek-ai/DeepSeek-V3.2-Exp",
            "deepseek-chat",
      
        ],
        "graph_models": [
            "deepseek-ai/DeepSeek-V3.2",
    
        ],
    },
    "iflow": {
        "name": "Iflow",
        "base_url": "https://apis.iflow.cn/v1",
        "api_key_env": "IFLOW_API_KEY",
        "agent_models": [
            "qwen3-max",
       
        ],
        "graph_models": [
            "qwen3-max",
           
        ],
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "agent_models": [
            "anthropic/claude-haiku-4.5",
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5-mini",
            "openai/gpt-5.2",
            "google/gemini-3-flash-preview",
            "google/gemini-3-pro-preview",
            "qwen/qwen3-vl-235b-a22b-instruct",
            "qwen/qwen3-next-80b-a3b-instruct",
            "openai/gpt-4o-mini",
        ],
        "graph_models": [
            "anthropic/claude-haiku-4.5",
            "anthropic/claude-sonnet-4.5",
            "openai/gpt-5-mini",
            "openai/gpt-5.2",
            "google/gemini-3-flash-preview",
            "google/gemini-3-pro-preview",
            "qwen/qwen3-vl-235b-a22b-instruct",
            "qwen/qwen3-next-80b-a3b-instruct",
            "openai/gpt-4o-mini",
            "z-ai/glm-4.6v",
        ],
    },
}


def get_provider_config(provider: str):
    """获取供应商配置"""
    return PROVIDERS.get(provider.lower())


def get_available_models(provider: str, role: str = "agent"):
    """获取指定供应商的模型列表"""
    cfg = get_provider_config(provider)
    if not cfg:
        return []
    return cfg["agent_models"] if role == "agent" else cfg["graph_models"]


def get_all_providers():
    """获取所有供应商列表"""
    return [{"id": k, "name": v["name"]} for k, v in PROVIDERS.items()]
