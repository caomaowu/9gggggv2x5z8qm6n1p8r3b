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

# A/B测试配置（已禁用，仅支持单一版本）
AB_TEST_CONFIG = {
    "enabled": False,
    "split_ratio": 1.0, 
    "tracking_enabled": True,
    "results_file": "ab_test_results.json"
}

# 版本使用统计配置
USAGE_TRACKING_CONFIG = {
    "enabled": True,
    "track_performance": True,
    "track_user_preferences": True,
    "auto_cleanup_days": 30  # 30天后自动清理统计数据
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

# 配置验证
def validate_config() -> bool:
    """验证配置的完整性"""
    required_keys = ["name", "description", "characteristics", "features", "limitations"]

    for version, config in DECISION_AGENT_VERSIONS.items():
        for key in required_keys:
            if key not in config:
                print(f"配置验证失败：版本 {version} 缺少必需字段 {key}")
                return False

    return True

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
