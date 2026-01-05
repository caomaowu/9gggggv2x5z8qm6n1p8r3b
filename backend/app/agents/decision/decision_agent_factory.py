"""
决策智能体工厂模式实现
支持根据配置动态创建不同版本的决策智能体
"""

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

# 哈雷酱的模块化导入！
import sys
from pathlib import Path
# sys.path hack removed

from .decision_configs import (
    DECISION_AGENT_VERSIONS,
    DEFAULT_DECISION_VERSION,
    USAGE_TRACKING_CONFIG,
    get_version_info,
    is_valid_version,
    get_default_version
)

# 导入不同版本的决策智能体
try:
    from .decision_agent import create_final_trade_decider
    from .decision_agent_relaxed import create_final_trade_decider_relaxed
    from .decision_agent_comprehensive import create_final_trade_decider_comprehensive
except ImportError as e:
    print(f"导入决策智能体模块失败: {e}")
    # 提供空函数避免破坏
    def create_final_trade_decider(llm):
        return lambda state: {"error": "约束版本决策智能体导入失败"}
    def create_final_trade_decider_relaxed(llm):
        return lambda state: {"error": "宽松版本决策智能体导入失败"}

# 版本使用统计
usage_stats = {
    "version_counts": {},
    "version_results": {},
    "last_reset": datetime.now().isoformat()
}

class DecisionAgentFactory:
    """决策智能体工厂类"""

    SUPPORTED_VERSIONS = {
    "constrained": create_final_trade_decider,
    "relaxed": create_final_trade_decider_relaxed,
    "comprehensive": create_final_trade_decider_comprehensive
    }

    def __init__(self):
        """初始化工厂"""
        self._validate_versions()
        self._init_usage_stats()

    def _validate_versions(self):
        """验证支持的有效版本"""
        valid_versions = set(DECISION_AGENT_VERSIONS.keys())
        factory_versions = set(self.SUPPORTED_VERSIONS.keys())

        missing_versions = valid_versions - factory_versions
        if missing_versions:
            print(f"警告：以下版本配置存在但工厂不支持: {missing_versions}")

        extra_versions = factory_versions - valid_versions
        if extra_versions:
            print(f"警告：工厂支持但配置中不存在的版本: {extra_versions}")

    def _init_usage_stats(self):
        """初始化使用统计"""
        global usage_stats
        for version in DECISION_AGENT_VERSIONS.keys():
            if version not in usage_stats["version_counts"]:
                usage_stats["version_counts"][version] = 0
            if version not in usage_stats["version_results"]:
                usage_stats["version_results"][version] = []

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

        # 验证版本有效性
        if not is_valid_version(version):
            print(f"警告：无效版本 '{version}'，使用默认版本 '{get_default_version()}'")
            version = get_default_version()

        # 记录使用统计
        if USAGE_TRACKING_CONFIG.get("enabled", True):
            self._track_usage(version)

        # 创建智能体
        try:
            creator_func = self.SUPPORTED_VERSIONS[version]
            agent = creator_func(llm, **kwargs)

            # 包装智能体以添加版本信息
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
            except:
                pass

            # 最后的降级：返回错误处理智能体
            return lambda state: {
                "error": f"所有决策智能体版本都不可用: {str(e)}",
                "agent_version": "error"
            }

    def _determine_version_from_env(self) -> str:
        """从环境变量确定版本"""
        # 优先级：环境变量 > 配置文件 > 默认值
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
                result["agent_version_name"] = DECISION_AGENT_VERSIONS[version]["name"]
                result["agent_version_description"] = DECISION_AGENT_VERSIONS[version]["description"]

            # 记录结果统计
            if USAGE_TRACKING_CONFIG.get("track_performance", True):
                self._track_result(version, result)

            return result

        return wrapped_agent

    def _track_usage(self, version: str):
        """记录版本使用统计"""
        global usage_stats
        usage_stats["version_counts"][version] = usage_stats["version_counts"].get(version, 0) + 1

    def _track_result(self, version: str, result: dict):
        """记录版本结果统计"""
        global usage_stats
        if version not in usage_stats["version_results"]:
            usage_stats["version_results"][version] = []

        # 只记录关键信息，避免存储过多数据
        result_summary = {
            "timestamp": datetime.now().isoformat(),
            "success": "error" not in result,
            "decision": result.get("final_trade_decision", "")[:100]  # 只保存前100个字符
        }

        usage_stats["version_results"][version].append(result_summary)

        # 限制历史记录数量
        max_results = 1000
        if len(usage_stats["version_results"][version]) > max_results:
            usage_stats["version_results"][version] = usage_stats["version_results"][version][-max_results:]

    def get_usage_stats(self) -> Dict[str, Any]:
        """获取使用统计信息"""
        global usage_stats
        return usage_stats.copy()

    def reset_usage_stats(self):
        """重置使用统计"""
        global usage_stats
        usage_stats = {
            "version_counts": {},
            "version_results": {},
            "last_reset": datetime.now().isoformat()
        }
        self._init_usage_stats()

    def get_version_comparison(self) -> Dict[str, Any]:
        """获取版本对比信息"""
        comparison = {}
        for version, config in DECISION_AGENT_VERSIONS.items():
            usage_count = usage_stats["version_counts"].get(version, 0)
            comparison[version] = {
                "name": config["name"],
                "description": config["description"],
                "usage_count": usage_count,
                "features": config.get("features", []),
                "limitations": config.get("limitations", [])
            }
        return comparison

    def recommend_version(self, market_conditions: Dict[str, Any] = None) -> str:
        """基于市场条件推荐版本"""
        if market_conditions is None:
            return get_default_version()

        # 简单的推荐逻辑
        complexity = market_conditions.get("complexity", "medium")
        volatility = market_conditions.get("volatility", "medium")

        # 高复杂度或高波动性推荐宽松版本
        if complexity in ["high", "very_high"] or volatility in ["high", "very_high"]:
            return "relaxed"

        # 低复杂度和低波动性推荐约束版本
        if complexity in ["low", "very_low"] and volatility in ["low", "very_low"]:
            return "constrained"

        # 其他情况使用默认版本
        return get_default_version()

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

def get_available_versions() -> Dict[str, str]:
    """获取所有可用版本"""
    return {version: info["name"] for version, info in DECISION_AGENT_VERSIONS.items()}

def get_version_usage_stats() -> Dict[str, Any]:
    """获取版本使用统计"""
    factory = get_decision_agent_factory()
    return factory.get_usage_stats()
