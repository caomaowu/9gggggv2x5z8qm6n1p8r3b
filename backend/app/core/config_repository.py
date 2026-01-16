import os
from typing import Dict, Optional
from pydantic import SecretStr


class ConfigRepository:
    """配置持久化仓库 - 负责读写 .env 文件"""
    
    def __init__(self, env_path: str = ".env"):
        self.env_path = env_path
    
    def update_env_file(self, updates: Dict[str, str]) -> bool:
        """
        更新 .env 文件并保留注释和格式
        
        Args:
            updates: 要更新的键值对字典
            
        Returns:
            是否成功更新
        """
        if not os.path.exists(self.env_path):
            return False

        try:
            with open(self.env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            updated_keys = set()
            
            for line in lines:
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith("#"):
                    new_lines.append(line)
                    continue
                
                key = line_stripped.split("=", 1)[0].strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            
            for key, value in updates.items():
                if key not in updated_keys:
                    new_lines.append(f"{key}={value}\n")

            with open(self.env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
                
            return True
        except Exception:
            return False
    
    def read_env_value(self, key: str) -> Optional[str]:
        """读取环境变量值"""
        return os.getenv(key)
    
    def read_secret_value(self, key: str) -> Optional[SecretStr]:
        """读取敏感值，返回 SecretStr"""
        value = os.getenv(key)
        if value:
            return SecretStr(value)
        return None


global_config_repository = ConfigRepository()
