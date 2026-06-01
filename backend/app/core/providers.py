"""预定义的 LLM 供应商和模型列表"""

PROVIDERS = {
    "modelscope": {
        "name": "ModelScope",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key_env": "MODELSCOPE_API_KEY",
        "agent_models": [
            "Qwen/Qwen3-Next-80B-A3B-Instruct",
            "Qwen/Qwen3-235B-A22B-Instruct",
            "deepseek-ai/DeepSeek-V4-Flash",
            "MiniMax/MiniMax-M2.7",
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
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ],
        "graph_models": [
            "deepseek-v4-flash",
            "deepseek-v4-pro",
        ],
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "agent_models": [
            "moonshotai/kimi-k2.5",



            "qwen/qwen3-next-80b-a3b-instruct",

            "stepfun/step-3.5-flash",
            "deepseek/deepseek-v4-flash",
            "tencent/hy3-preview",
            "minimax/minimax-m3",
        ],
        "graph_models": [




            "qwen/qwen3-next-80b-a3b-instruct",

            "stepfun/step-3.5-flash",
            "deepseek/deepseek-v4-flash",
            "tencent/hy3-preview",
            "minimax/minimax-m3",
        ],
    },
    "soul": {
        "name": "Soul",
        "base_url": "https://api.souimagery.fun/v1",
        "api_key_env": "SOUL_API_KEY",
        "agent_models": [

            "gpt-5.4",

        ],
        "graph_models": [

            "gpt-5.4",


        ],
    },
    "302ai": {
        "name": "302AI",
        "base_url": "https://api.302.ai/v1",
        "api_key_env": "API302_API_KEY",
        "agent_models": [


            "qwen3.5-flash",
            "qwen3.6-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "gemini-3.1-flash-lite-preview",
            "step-3.5-flash",


            "MiniMax-M3",
        ],
        "graph_models": [
   
            "qwen3.5-flash",
            "qwen3.6-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",

            "gemini-3.1-flash-lite-preview",
            "step-3.5-flash",

            "MiniMax-M3",
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
