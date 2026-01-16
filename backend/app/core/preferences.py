import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

# 定义偏好文件的路径
# 假设 backend 是当前工作目录的子目录，或者我们在 backend/app/core 下
# 我们将文件存在 backend/data/llm_preferences.json
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PREFS_FILE = DATA_DIR / "llm_preferences.json"

class PreferencesManager:
    def __init__(self):
        self._ensure_data_dir()
        self._preferences = self._load_preferences()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        if not DATA_DIR.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)

    def _load_preferences(self) -> Dict[str, Any]:
        """加载偏好设置"""
        if not PREFS_FILE.exists():
            return {}
        try:
            with open(PREFS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading preferences: {e}")
            return {}

    def _save_preferences(self):
        """保存偏好设置"""
        try:
            with open(PREFS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._preferences, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving preferences: {e}")

    def get_model_temperature(self, model: str, default: float = 0.1, role: Optional[str] = None) -> float:
        """获取指定模型的温度偏好，支持按角色区分"""
        legacy_map = self._preferences.get("model_temperatures", {})
        
        if role == "agent":
            agent_map = self._preferences.get("agent_model_temperatures", {})
            if model in agent_map:
                return agent_map[model]
            return legacy_map.get(model, default)
        
        if role == "graph":
            graph_map = self._preferences.get("graph_model_temperatures", {})
            if model in graph_map:
                return graph_map[model]
            return legacy_map.get(model, default)
        
        return legacy_map.get(model, default)

    def set_model_temperature(self, model: str, temperature: float, role: Optional[str] = None):
        """设置指定模型的温度偏好，可按角色区分"""
        if role == "agent":
            if "agent_model_temperatures" not in self._preferences:
                self._preferences["agent_model_temperatures"] = {}
            self._preferences["agent_model_temperatures"][model] = temperature
        elif role == "graph":
            if "graph_model_temperatures" not in self._preferences:
                self._preferences["graph_model_temperatures"] = {}
            self._preferences["graph_model_temperatures"][model] = temperature
        else:
            if "model_temperatures" not in self._preferences:
                self._preferences["model_temperatures"] = {}
            self._preferences["model_temperatures"][model] = temperature

        self._save_preferences()

    def get_all_model_temperatures(self) -> Dict[str, float]:
        """获取所有模型的温度偏好"""
        return self._preferences.get("model_temperatures", {})

    def get_all_model_temperatures_by_role(self, role: str) -> Dict[str, float]:
        """按角色获取模型温度偏好，合并 legacy 数据"""
        legacy_map = self._preferences.get("model_temperatures", {}) or {}
        if role == "agent":
            agent_map = self._preferences.get("agent_model_temperatures", {}) or {}
            merged = {**legacy_map, **agent_map}
            return merged
        if role == "graph":
            graph_map = self._preferences.get("graph_model_temperatures", {}) or {}
            merged = {**legacy_map, **graph_map}
            return merged
        return legacy_map

# 全局单例
preferences_manager = PreferencesManager()
