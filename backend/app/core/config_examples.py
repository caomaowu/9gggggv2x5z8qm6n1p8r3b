"""
LLM 配置系统使用示例

这个模块展示了如何灵活使用新的 LLM 配置系统，
支持在不同供应商之间轻松切换。
"""

from app.core.config import (
    settings, 
    config, 
    create_llm_client, 
    get_llm_info,
    LLMProvider
)
from langchain_openai import ChatOpenAI


# ===========================================
# 示例 1: 使用全局配置（推荐用于生产环境）
# ===========================================
def example_global_config():
    """使用全局配置获取当前 LLM 设置"""
    print("=" * 60)
    print("示例 1: 使用全局配置")
    print("=" * 60)
    
    # 获取当前 Agent LLM 配置
    agent_info = get_llm_info(role="agent")
    print(f"Agent 供应商: {agent_info['name']}")
    print(f"Agent 模型: {agent_info['model']}")
    print(f"Agent 温度: {agent_info['temperature']}")
    print(f"API Base URL: {agent_info['base_url']}")
    
    # 获取当前 Graph LLM 配置
    graph_info = get_llm_info(role="graph")
    print(f"\nGraph 供应商: {graph_info['name']}")
    print(f"Graph 模型: {graph_info['model']}")
    
    print()


# ===========================================
# 示例 2: 动态切换供应商
# ===========================================
def example_switch_provider():
    """演示如何动态切换 LLM 供应商"""
    print("=" * 60)
    print("示例 2: 动态切换供应商")
    print("=" * 60)
    
    # 切换 Agent 使用 DeepSeek
    config.set_agent_provider("deepseek", "deepseek-ai/DeepSeek-V3.2-Exp")
    print("已切换 Agent 到 DeepSeek")
    print(f"Agent 模型: {config.llm.agent_model}")
    
    # 切换 Graph 使用 OpenAI
    config.set_graph_provider("openai", "gpt-4o")
    print("\n已切换 Graph 到 OpenAI")
    print(f"Graph 模型: {config.llm.graph_model}")
    
    # 恢复使用 ModelScope（默认）
    config.set_agent_provider("modelscope")
    config.set_graph_provider("modelscope")
    print("\n已恢复到 ModelScope")
    
    print()


# ===========================================
# 示例 3: 使用工厂函数创建 LLM 客户端
# ===========================================
def example_factory_function():
    """使用工厂函数创建 LLM 客户端（推荐用于测试和临时切换）"""
    print("=" * 60)
    print("示例 3: 使用工厂函数创建 LLM 客户端")
    print("=" * 60)
    
    # 使用当前配置创建 Agent LLM
    agent_llm = create_llm_client(role="agent")
    print(f"Agent LLM: {agent_llm.model_name}")
    
    # 临时使用 DeepSeek 创建 Agent LLM
    temp_agent_llm = create_llm_client(
        provider="deepseek", 
        model="deepseek-ai/DeepSeek-V3.2-Exp",
        role="agent"
    )
    print(f"临时 Agent LLM (DeepSeek): {temp_agent_llm.model_name}")
    
    # 使用自定义温度创建 Graph LLM
    graph_llm = create_llm_client(role="graph", temperature=0.2)
    print(f"Graph LLM: {graph_llm.model_name} (温度: {graph_llm.temperature})")
    
    print()


# ===========================================
# 示例 4: 获取可用模型列表
# ===========================================
def example_available_models():
    """获取特定供应商的可用模型列表"""
    print("=" * 60)
    print("示例 4: 获取可用模型列表")
    print("=" * 60)
    
    # 获取所有可用供应商
    providers = settings.get_all_providers()
    print("可用供应商:")
    for p in providers:
        print(f"  - {p['name']} ({p['id']})")
    
    # 获取特定供应商的模型
    print("\nDeepSeek Agent 模型:")
    deepseek_agent_models = settings.get_available_models(provider="deepseek", role="agent")
    for model in deepseek_agent_models:
        print(f"  - {model}")
    
    print("\nOpenAI Graph 模型:")
    openai_graph_models = settings.get_available_models(provider="openai", role="graph")
    for model in openai_graph_models:
        print(f"  - {model}")
    
    print()


# ===========================================
# 示例 5: 获取完整配置信息
# ===========================================
def example_full_config():
    """获取当前完整配置信息"""
    print("=" * 60)
    print("示例 5: 获取完整配置信息")
    print("=" * 60)
    
    full_config = config.get_current_config()
    
    print("Agent 配置:")
    print(f"  供应商: {full_config['agent']['name']}")
    print(f"  模型: {full_config['agent']['model']}")
    
    print("\nGraph 配置:")
    print(f"  供应商: {full_config['graph']['name']}")
    print(f"  模型: {full_config['graph']['model']}")
    
    print("\nAgent 可用模型:")
    for model in full_config['agent_models']:
        print(f"  - {model}")
    
    print("\nGraph 可用模型:")
    for model in full_config['graph_models']:
        print(f"  - {model}")
    
    print()


# ===========================================
# 示例 6: 传统使用方式（向后兼容）
# ===========================================
def example_backward_compatibility():
    """演示传统使用方式（向后兼容）"""
    print("=" * 60)
    print("示例 6: 传统使用方式（向后兼容）")
    print("=" * 60)
    
    # 使用 config.llm 的方式
    print(f"Agent 模型: {config.llm.agent_model}")
    print(f"Graph 模型: {config.llm.graph_model}")
    print(f"API Key: {config.llm.api_key[:10]}...")
    print(f"Base URL: {config.llm.base_url}")
    
    print()


# ===========================================
# 主函数
# ===========================================
def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("LLM 配置系统使用示例")
    print("=" * 60 + "\n")
    
    example_global_config()
    example_switch_provider()
    example_factory_function()
    example_available_models()
    example_full_config()
    example_backward_compatibility()
    
    print("=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
