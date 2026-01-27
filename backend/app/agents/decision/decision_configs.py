"""
决策智能体配置管理模块
管理不同版本的决策智能体配置和版本信息
"""

# 版本配置
DECISION_AGENT_VERSIONS = {
    "original": {
        "name": "原始经典版",
        "description": "经过实战验证的原始高频交易逻辑，保留英文Prompt，强制二选一",
        "characteristics": [
            "决策范围：LONG/SHORT（HFT约束）",
            "Prompt语言：英文 (Original)",
            "风险回报比：1.2-1.8",
            "核心逻辑：三报告一致性优先"
        ],
        "features": [
            "🏆 经过实战验证",
            "⚡ 纯粹的HFT逻辑",
            "🎯 英文原版Prompt"
        ],
        "limitations": [
            "❌ 不支持观望 (HOLD prohibited)",
            "❌ 不包含最新市场环境分类逻辑"
        ]
    }
}

# 默认配置
DEFAULT_DECISION_VERSION = "original"

# 版本描述映射
VERSION_DESCRIPTIONS = {
    "original": "原始经典版：经过实战验证的HFT逻辑，英文Prompt，强制二选一"
}

def get_version_info(version: str) -> dict:
    """获取指定版本的详细信息"""
    return DECISION_AGENT_VERSIONS.get(version, {})

def get_all_versions() -> dict:
    """获取所有可用版本信息"""
    return DECISION_AGENT_VERSIONS

def get_version_description(version: str) -> str:
    """获取版本描述"""
    return VERSION_DESCRIPTIONS.get(version, "未知版本")

def is_valid_version(version: str) -> bool:
    """检查版本是否有效"""
    return version in DECISION_AGENT_VERSIONS

def get_default_version() -> str:
    """获取默认版本"""
    return DEFAULT_DECISION_VERSION

def get_version_characteristics(version: str) -> list:
    """获取版本特征列表"""
    version_info = get_version_info(version)
    return version_info.get("characteristics", [])

def get_version_features(version: str) -> list:
    """获取版本优点列表"""
    version_info = get_version_info(version)
    return version_info.get("features", [])

def get_version_limitations(version: str) -> list:
    """获取版本限制列表"""
    version_info = get_version_info(version)
    return version_info.get("limitations", [])

# 推荐版本功能
def recommend_version(market_complexity: str = "medium",
                     user_preference: str = "balanced") -> str:
    """根据市场复杂度和用户偏好推荐版本"""
    # 由于只保留了 original 版本，直接返回默认版本
    return get_default_version()

# 风控参数配置
risk_control = {
    "floor_pct": 0.003,
    "rr_lo": 1.3,
    "rr_hi": 1.8,
    "vol_floor_map": {
        "低波动性": 0.003,
        "中等波动性": 0.005,
        "高波动性": 0.008
    }
}
