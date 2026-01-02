"""
双模型配置管理器
哈雷酱的专业双模型配置管理！(￣▽￣)／

这个模块专门负责双模型决策系统的配置管理，
包括模型选择、状态持久化、用户偏好等功能。
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


class DualModelConfigManager:
    """双模型配置管理器"""

    def __init__(self, config_file: str = None):
        """初始化配置管理器"""
        if config_file is None:
            config_file = PROJECT_ROOT / "config" / "dual_model_config.json"

        self.config_file = Path(config_file)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "dual_model": {
                "enabled": False,
                "model_1": "MiniMax/MiniMax-M2",
                "model_2": "deepseek-ai/DeepSeek-V3.2-Exp",
                "temperature_1": 0.1,
                "temperature_2": 0.1,
                "last_updated": datetime.now().isoformat() + "Z"
            },
            "user_preferences": {
                "auto_save": True,
                "show_comparison": True,
                "color_coding": True
            },
            "version": "1.0.0",
            "description": "哈雷酱的双模型决策系统配置文件"
        }

        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并默认配置，确保所有字段都存在
                    return self._merge_configs(default_config, loaded_config)
            except Exception as e:
                print(f"哈雷酱警告：加载配置文件失败: {e}，使用默认配置")
                return default_config
        else:
            # 创建默认配置文件
            self._save_config(default_config)
            return default_config

    def _merge_configs(self, default: Dict, loaded: Dict) -> Dict:
        """合并配置，优先使用已加载的配置"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def _save_config(self, config: Dict[str, Any] = None) -> None:
        """保存配置到文件"""
        if config is None:
            config = self.config

        try:
            # 确保配置目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            # 更新时间戳
            if "dual_model" in config:
                config["dual_model"]["last_updated"] = datetime.now().isoformat() + "Z"

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"哈雷酱错误：保存配置文件失败: {e}")

    def is_dual_model_enabled(self) -> bool:
        """检查是否启用双模型模式"""
        return self.config.get("dual_model", {}).get("enabled", False)

    def enable_dual_model(self, model_1: str, model_2: str,
                         temperature_1: float = 0.1, temperature_2: float = 0.1) -> None:
        """启用双模型模式"""
        self.config["dual_model"].update({
            "enabled": True,
            "model_1": model_1,
            "model_2": model_2,
            "temperature_1": temperature_1,
            "temperature_2": temperature_2,
            "last_updated": datetime.now().isoformat() + "Z"
        })

        if self.config.get("user_preferences", {}).get("auto_save", True):
            self._save_config()

    def disable_dual_model(self) -> None:
        """禁用双模型模式"""
        self.config["dual_model"]["enabled"] = False
        self.config["dual_model"]["last_updated"] = datetime.now().isoformat() + "Z"

        if self.config.get("user_preferences", {}).get("auto_save", True):
            self._save_config()

    def get_dual_model_config(self) -> Dict[str, Any]:
        """获取双模型配置"""
        return self.config.get("dual_model", {}).copy()

    def get_model_config(self, model_index: int) -> Dict[str, Any]:
        """获取指定模型的配置"""
        dual_config = self.config.get("dual_model", {})
        if model_index == 1:
            return {
                "model": dual_config.get("model_1", ""),
                "temperature": dual_config.get("temperature_1", 0.1)
            }
        elif model_index == 2:
            return {
                "model": dual_config.get("model_2", ""),
                "temperature": dual_config.get("temperature_2", 0.1)
            }
        return {}

    def update_user_preferences(self, preferences: Dict[str, Any]) -> None:
        """更新用户偏好设置"""
        if "user_preferences" not in self.config:
            self.config["user_preferences"] = {}

        self.config["user_preferences"].update(preferences)

        if self.config.get("user_preferences", {}).get("auto_save", True):
            self._save_config()

    def get_user_preferences(self) -> Dict[str, Any]:
        """获取用户偏好设置"""
        return self.config.get("user_preferences", {}).copy()

    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self.config = self._load_config()
        self._save_config()

    def export_config(self) -> str:
        """导出配置为JSON字符串"""
        return json.dumps(self.config, ensure_ascii=False, indent=2)

    def import_config(self, config_json: str) -> bool:
        """从JSON字符串导入配置"""
        try:
            imported_config = json.loads(config_json)
            # 验证配置格式
            if self._validate_config(imported_config):
                self.config = imported_config
                self._save_config()
                return True
            else:
                print("哈雷酱警告：配置格式验证失败")
                return False
        except Exception as e:
            print(f"哈雷酱错误：导入配置失败: {e}")
            return False

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """验证配置格式"""
        required_keys = ["dual_model", "user_preferences"]
        for key in required_keys:
            if key not in config:
                return False

        dual_model = config["dual_model"]
        required_dual_keys = ["enabled", "model_1", "model_2"]
        for key in required_dual_keys:
            if key not in dual_model:
                return False

        return True

    def get_config_summary(self) -> str:
        """获取配置摘要"""
        dual_config = self.config.get("dual_model", {})
        enabled = dual_config.get("enabled", False)

        if enabled:
            model_1 = dual_config.get("model_1", "未知")
            model_2 = dual_config.get("model_2", "未知")
            return f"双模型模式已启用：{model_1} vs {model_2}"
        else:
            model = dual_config.get("model_1", "默认模型")
            return f"单模型模式：{model}"


# 全局配置管理器实例
_dual_config_manager = None


def get_dual_model_config_manager() -> DualModelConfigManager:
    """获取全局双模型配置管理器实例（单例模式）"""
    global _dual_config_manager
    if _dual_config_manager is None:
        _dual_config_manager = DualModelConfigManager()
    return _dual_config_manager


# 便捷函数
def is_dual_model_enabled() -> bool:
    """检查是否启用双模型模式"""
    return get_dual_model_config_manager().is_dual_model_enabled()


def get_dual_model_config() -> Dict[str, Any]:
    """获取双模型配置"""
    return get_dual_model_config_manager().get_dual_model_config()


def enable_dual_model(model_1: str, model_2: str,
                     temperature_1: float = 0.1, temperature_2: float = 0.1) -> None:
    """启用双模型模式"""
    get_dual_model_config_manager().enable_dual_model(model_1, model_2, temperature_1, temperature_2)


def disable_dual_model() -> None:
    """禁用双模型模式"""
    get_dual_model_config_manager().disable_dual_model()