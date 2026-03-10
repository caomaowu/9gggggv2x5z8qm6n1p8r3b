import os
from typing import Dict, Any

def get_env_path() -> str:
    """获取 .env 文件路径"""
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        # Try looking one level up
        env_path_up = os.path.join(os.path.dirname(os.getcwd()), ".env")
        if os.path.exists(env_path_up):
            env_path = env_path_up
        elif os.path.exists(os.path.join(os.getcwd(), "backend", ".env")):
            env_path = os.path.join(os.getcwd(), "backend", ".env")
    return env_path

def read_env_config() -> Dict[str, str]:
    """读取 .env 配置"""
    env_path = get_env_path()
    config = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
    return config

def update_env_config(updates: Dict[str, Any]) -> None:
    """更新 .env 配置"""
    env_path = get_env_path()
    
    if not os.path.exists(env_path):
        # 如果不存在，创建一个新的
        with open(env_path, "w", encoding="utf-8") as f:
            for key, value in updates.items():
                f.write(f"{key}={value}\n")
        return

    # 读取现有内容
    with open(env_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    updated_keys = set()
    
    # 更新现有行
    for line in lines:
        stripped_line = line.strip()
        if stripped_line and not stripped_line.startswith("#") and "=" in stripped_line:
            key = stripped_line.split("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    # 添加新行
    for key, value in updates.items():
        if key not in updated_keys:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append(f"{key}={value}\n")

    # 写入文件
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
