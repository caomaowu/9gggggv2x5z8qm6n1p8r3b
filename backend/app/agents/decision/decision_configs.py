"""
决策智能体配置管理模块
管理不同版本的决策智能体配置和版本信息
"""

# 版本配置
DECISION_AGENT_VERSIONS = {
    "original": {
        "name": "原始经典版",
        "description": "严格信号确认版，分别预测主周期 K1/K2，支持观望",
        "characteristics": [
            "决策范围：K1/K2 独立 LONG/SHORT/HOLD",
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
            "❌ 严格确认可能降低覆盖率",
            "❌ 不包含最新市场环境分类逻辑"
        ]
    },
    "lite": {
        "name": "轻量极速版",
        "description": "精简版 Prompt，利用大模型直觉进行快速综合判断，减少死板规则",
        "characteristics": [
            "决策范围：LONG/SHORT/HOLD",
            "Prompt语言：英文 (Lite)",
            "风险回报比：1.2-2.5",
            "核心逻辑：大模型直觉 + 信号融合"
        ],
        "features": [
            "🚀 速度极快",
            "🧠 减少过度思考",
            "🎯 更加灵活"
        ],
        "limitations": [
            "❌ 可能牺牲部分严格性",
            "❌ 依赖模型自身的逻辑能力"
        ]
    }
}

# 默认配置
DEFAULT_DECISION_VERSION = "lite"  # 默认使用轻量版以提高响应速度

# 版本描述映射
VERSION_DESCRIPTIONS = {
    "original": "原始经典版：经过实战验证的HFT逻辑，英文Prompt，强制二选一",
    "lite": "轻量极速版：精简Prompt，利用大模型直觉，速度快，避免过度思考"
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
