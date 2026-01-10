import json
import os
import time
from typing import Dict, Optional, Any, List
from pydantic import BaseModel, Field

# 简化后的数据模型，移除所有锁定相关字段
class AuthState(BaseModel):
    is_enabled: bool = True  # 仅保留开关状态

class AuthService:
    def __init__(self, storage_file: str = "data/auth_storage.json"):
        # 获取 backend 根目录的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
        
        # 强制指定 data 目录路径
        data_dir = os.path.join(backend_dir, "data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            
        self.storage_file = os.path.join(backend_dir, storage_file)
        
        self.user_password = "11223344a"
        self.admin_password = "11223344aA"
        self.token_validity = 72 * 3600    # Token 有效期保持不变
        
        self._load_state()

    def _load_state(self):
        """加载持久化状态"""
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 兼容旧数据，只读取需要的字段
                    self.state = AuthState(is_enabled=data.get("is_enabled", True))
            except Exception as e:
                print(f"Error loading auth state: {e}")
                self.state = AuthState()
        else:
            self.state = AuthState()
            self._save_state()

    def _save_state(self):
        """保存状态到文件"""
        try:
            os.makedirs(os.path.dirname(self.storage_file), exist_ok=True)
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.state.model_dump(), f, indent=2)
        except Exception as e:
            print(f"Error saving auth state: {e}")

    def is_system_enabled(self) -> bool:
        return self.state.is_enabled

    def toggle_system(self, admin_password: str, enabled: bool) -> bool:
        if admin_password != self.admin_password:
            return False
        self.state.is_enabled = enabled
        self._save_state()
        return True

    # --- 锁定相关方法桩 (保留方法签名以兼容 API 调用，但移除实际逻辑) ---

    def is_ip_locked(self, ip: str) -> bool:
        """永远返回 False，不再锁定任何 IP"""
        return False

    def get_remaining_attempts(self, ip: str) -> int:
        """永远返回一个较大的数字，表示无限尝试"""
        return 9999

    def verify_password(self, password: str, ip: str) -> Dict[str, Any]:
        """
        验证密码 (无锁定逻辑版)
        """
        # 1. 验证密码
        if password == self.user_password:
            # 生成简单的 Token
            expiry = time.time() + self.token_validity
            return {
                "success": True,
                "message": "验证成功",
                "locked": False,
                "token": f"auth_{int(expiry)}",
                "expires_at": expiry
            }

        # 2. 密码错误
        return {
            "success": False,
            "message": "密码错误，请重试。",
            "locked": False,
            "remaining_attempts": 9999 # 无限尝试
        }

# 全局实例
auth_service = AuthService()
