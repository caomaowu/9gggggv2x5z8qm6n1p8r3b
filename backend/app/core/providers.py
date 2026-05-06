"""预定义的 LLM 供应商和模型列表"""

PROVIDERS = {
    "modelscope": {
        "name": "ModelScope",
        "base_url": "https://api-inference.modelscope.cn/v1",
        "api_key_env": "MODELSCOPE_API_KEY",
        "agent_models": [
            "Qwen/Qwen3-Next-80B-A3B-Instruct",
            "Qwen/Qwen3-235B-A22B-Instruct",
            "ZhipuAI/GLM-4.7",
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
    "iflow": {
        "name": "Iflow",
        "base_url": "https://apis.iflow.cn/v1",
        "api_key_env": "IFLOW_API_KEY",
        "agent_models": [
            "qwen3-max",
            "kimi-k2-0905",
            "qwen3-235b-a22b-instruct",
        ],
        "graph_models": [
            "qwen3-max",
            "qwen3-vl-plus",
           
        ],
    },
    "iflow2": {
        "name": "Iflow2",
        "base_url": "https://apis.iflow.cn/v1",
        "api_key_env": "IFLOW2_API_KEY",
        "agent_models": [
            "qwen3-max",
            "kimi-k2-0905",
            "qwen3-235b-a22b-instruct",
        ],
        "graph_models": [
            "qwen3-max",
            "qwen3-vl-plus",
        ],
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "agent_models": [
            "anthropic/claude-haiku-4.5",
            "anthropic/claude-sonnet-4.5",
            "moonshotai/kimi-k2.5",
            "openai/gpt-5-mini",
            "openai/gpt-5.2",
            "google/gemini-3-flash-preview",
            "google/gemini-3-pro-preview",
            "qwen/qwen3-vl-235b-a22b-instruct",
            "qwen/qwen3-next-80b-a3b-instruct",
            "openai/gpt-4o-mini",
            "xiaomi/mimo-v2-flash:free",
        ],
        "graph_models": [
            "anthropic/claude-haiku-4.5",
            "anthropic/claude-sonnet-4.5",
            "moonshotai/kimi-k2.5",
            "openai/gpt-5-mini",
            "openai/gpt-5.2",
            "google/gemini-3-flash-preview",
            "google/gemini-3-pro-preview",
            "qwen/qwen3-vl-235b-a22b-instruct",
            "qwen/qwen3-next-80b-a3b-instruct",
            "openai/gpt-4o-mini",
            "z-ai/glm-4.6v",
            "nvidia/nemotron-nano-12b-v2-vl:free",
        ],
    },
    "ark": {
        "name": "Ark",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "api_key_env": "ARK_API_KEY",
        "agent_models": [
            "ark-code-latest",
        ],
        "graph_models": [
            "ark-code-latest",
        ],
    },
    "codex": {
        "name": "Codex",
        "base_url": "https://codex.caomaowu.lol/v1",
        "api_key_env": "CODEX_API_KEY",
        "agent_models": [
            "gpt-5.2",
            "gpt-5.2codex",
        ],
        "graph_models": [
            "gpt-5.2",
            "gpt-5.2codex",
        ],
    },
    "soul": {
        "name": "Soul",
        "base_url": "https://api.souimagery.fun/v1",
        "api_key_env": "SOUL_API_KEY",
        "agent_models": [
            "gpt-5.2",
            "gpt-5.3",
            "gpt-5.4",
            "gpt-5.3-codex",
            "gpt-5.4-mini",
        ],
        "graph_models": [
            "gpt-5.2",
            "gpt-5.3",
            "gpt-5.4",
            "gpt-5.3-codex",
            "gpt-5.4-mini",
        ],
    },
    "302ai": {
        "name": "302AI",
        "base_url": "https://api.302.ai/v1",
        "api_key_env": "API302_API_KEY",
        "agent_models": [
            "qwen3.5-plus",
            "Pro/moonshotai/Kimi-K2.5",
            "grok-4-fast-non-reasoning",
            "grok-4-1-fast-non-reasoning",
            "qwen3.5-flash",
            "qwen3.6-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "glm-4.6v-flash",
            "gemini-3.1-flash-lite-preview",
            "step-3.5-flash",
            "Doubao-Seed-2.0-mini",
            "Doubao-Seed-2.0-lite",
        ],
        "graph_models": [
            "qwen3.5-plus",
            "Pro/moonshotai/Kimi-K2.5",
            "grok-4-fast-non-reasoning",
            "grok-4-1-fast-non-reasoning",
            "qwen3.5-flash",
            "qwen3.6-flash",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "glm-4.6v-flash",
            "gemini-3.1-flash-lite-preview",
            "step-3.5-flash",
            "Doubao-Seed-2.0-mini",
            "Doubao-Seed-2.0-lite",
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
