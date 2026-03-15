"""
决策智能体工厂模式实现 (简化版)
支持根据配置动态创建不同版本的决策智能体，保留核心创建和降级功能，移除冗余统计。
"""

import os
from typing import Dict, Any, Optional

from .decision_configs import (
    DECISION_AGENT_VERSIONS,
    DEFAULT_DECISION_VERSION,
    get_version_info,
    is_valid_version,
    get_default_version
)

# 导入不同版本的决策智能体
try:
    from .decision_agent_original import create_final_trade_decider_original
except ImportError as e:
    print(f"导入决策智能体模块失败: {e}")
    # 提供空函数避免破坏
    def create_final_trade_decider_original(llm):
        return lambda state: {"error": "原始版本决策智能体导入失败"}

try:
    from .decision_agent_lite import create_final_trade_decider_lite
except ImportError as e:
    print(f"导入决策智能体模块失败: {e}")
    def create_final_trade_decider_lite(llm):
        return lambda state: {"error": "轻量版本决策智能体导入失败"}

class DecisionAgentFactory:
    """决策智能体工厂类 (精简版)"""

    SUPPORTED_VERSIONS = {
        "original": create_final_trade_decider_original,
        "lite": create_final_trade_decider_lite
    }

    def create_agent(self, version: str = None, llm=None, **kwargs):
        """
        根据版本创建决策智能体

        Args:
            version: 版本名称，如果为None则使用默认版本
            llm: 语言模型实例
            **kwargs: 其他参数

        Returns:
            决策智能体函数
        """
        # 确定使用的版本
        if version is None:
            version = self._determine_version_from_env()

        # 验证版本有效性，无效则回退到默认
        if not is_valid_version(version):
            print(f"警告：无效版本 '{version}'，使用默认版本 '{get_default_version()}'")
            version = get_default_version()

        # 创建智能体
        try:
            creator_func = self.SUPPORTED_VERSIONS.get(version)
            if not creator_func:
                # 再次检查，防止配置有但工厂未注册
                print(f"警告：工厂不支持版本 '{version}'，回退到默认")
                version = get_default_version()
                creator_func = self.SUPPORTED_VERSIONS[version]

            agent = creator_func(llm, **kwargs)

            # 简单包装：仅添加版本信息，移除复杂的统计逻辑
            wrapped_agent = self._wrap_agent_with_version_info(agent, version)

            print(f"✅ 成功创建 {version} 版本决策智能体")
            return wrapped_agent

        except Exception as e:
            print(f"❌ 创建 {version} 版本决策智能体失败: {e}")
            # 降级到默认版本
            try:
                default_version = get_default_version()
                if version != default_version:
                    print(f"🔄 尝试创建默认版本 {default_version}")
                    return self.create_agent(default_version, llm, **kwargs)
            except Exception as fallback_error:
                print(f"❌ 降级失败: {fallback_error}")

            # 最后的降级：返回错误处理智能体
            return lambda state: {
                "error": f"所有决策智能体版本都不可用: {str(e)}",
                "agent_version": "error"
            }

    def _determine_version_from_env(self) -> str:
        """从环境变量确定版本"""
        env_version = os.getenv("DECISION_AGENT_VERSION")
        if env_version and is_valid_version(env_version):
            return env_version
        return get_default_version()

    def _wrap_agent_with_version_info(self, agent_func, version: str):
        """包装智能体函数，添加版本信息"""
        def wrapped_agent(state):
            # 执行原始智能体
            result = agent_func(state)

            # 确保结果包含版本信息
            if isinstance(result, dict):
                result["agent_version"] = version
                # 从配置中获取元数据
                config = DECISION_AGENT_VERSIONS.get(version, {})
                result["agent_version_name"] = config.get("name", version)
                result["agent_version_description"] = config.get("description", "")

            return result

        return wrapped_agent

# 全局工厂实例
_factory_instance = None

def get_decision_agent_factory() -> DecisionAgentFactory:
    """获取决策智能体工厂实例（单例模式）"""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = DecisionAgentFactory()
    return _factory_instance

def create_decision_agent(version: str = None, llm=None, **kwargs):
    """便捷函数：创建决策智能体"""
    factory = get_decision_agent_factory()
    return factory.create_agent(version, llm, **kwargs)
