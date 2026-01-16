"""
决策智能体配置管理模块
管理不同版本的决策智能体配置和版本信息
"""

# 版本配置
DECISION_AGENT_VERSIONS = {
    "constrained": {
        "name": "约束版本",
        "description": "严格的决策规则，标准化输出格式，适合稳定交易",
        "characteristics": [
            "决策范围：做多/做空（二选一）",
            "风险回报比：1.1-1.8（固定范围）",
            "市场环境：趋势/震荡/突破（三种分类）",
            "输出格式：严格JSON格式",
            "适用场景：稳定市场环境，追求一致性"
        ],
        "features": [
            "✅ 决策效率高",
            "✅ 输出标准化",
            "✅ 风险控制严格",
            "✅ 回测友好"
        ],
        "limitations": [
            "❌ 缺乏观望选项",
            "❌ 灵活性不足",
            "❌ 无法处理复杂市场"
        ]
    },
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
    },
    "relaxed": {
        "name": "宽松版本",
        "description": "更自由的思维，支持观望选项，适合复杂市场环境",
        "characteristics": [
            "决策范围：做多/做空/观望（三选一）",
            "风险回报比：1.1-5.0（扩展范围）",
            "市场环境：精细化分类（9种环境）",
            "输出格式：灵活分析推理",
            "适用场景：复杂或不确定市场环境"
        ],
        "features": [
            "🆕 支持观望决策",
            "🆕 更自由的分析思维",
            "🆕 细化市场环境识别",
            "🆕 动态风险控制",
            "🆕 深度推理框架"
        ],
        "limitations": [
            "⚠️ 分析时间可能较长",
            "⚠️ 输出格式更多样化",
            "⚠️ 需要更多计算资源"
        ]
    },
    "comprehensive": {
        "name": "综合分析版",
        "description": "融合三报告与结构位/波动性依据，直接给出止损止盈，不使用风险回报比",
        "characteristics": [
            "决策范围：做多/做空/观望",
            "点位依据：支撑阻力/趋势线拐点/形态关键位",
            "波动性缓冲：ATR或标准差安全余量",
            "输出不含风险回报比"
        ],
        "features": [
            "✅ 结构化数值点位",
            "✅ 深度综合分析",
            "✅ 一致性权衡",
            "✅ 不依赖RR"
        ],
        "limitations": [
            "⚠️ 需更强的数据质量与结构位识别",
            "⚠️ 前端不展示RR相关信息"
        ]
    }
}

# 默认配置
DEFAULT_DECISION_VERSION = "original"

# 版本描述映射
VERSION_DESCRIPTIONS = {
    "original": "原始经典版：经过实战验证的HFT逻辑，英文Prompt，强制二选一",
    "constrained": "约束版本：严格的决策规则，标准化输出格式，适合稳定交易",
    "relaxed": "宽松版本：更自由的思维，支持观望选项，适合复杂市场环境",
    "comprehensive": "综合分析版：结构位与波动性依据，直接给出止损止盈，不含风险回报比"
}

# A/B测试配置（如果需要的话）
AB_TEST_CONFIG = {
    "enabled": False,
    "split_ratio": 0.5,  # 50%使用约束版本，50%使用宽松版本
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

    if market_complexity == "high" or user_preference == "flexible":
        return "relaxed"
    elif market_complexity == "low" or user_preference == "conservative":
        return "constrained"
    else:
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