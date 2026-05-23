import json
import os
import re
from typing import Any, Dict


def _tools_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _repo_root() -> str:
    return os.path.dirname(_tools_dir())


FAV_ASSETS_FILE = os.path.join(_tools_dir(), "data", "favorite_assets.json")
PRESETS_DIR = os.path.join(_tools_dir(), "data", "task_presets")
ENV_PATH = os.path.join(_repo_root(), "backend", ".env")

DAEMON_CONFIG_FILE = os.path.join(_tools_dir(), "data", "daemon_config.json")
DAEMON_PROGRESS_FILE = os.path.join(_tools_dir(), "data", "batch_backtest_progress.json")
DAEMON_STATUS_FILE = os.path.join(_tools_dir(), "data", "batch_backtest_status.json")


def get_favorites() -> list[str]:
    if not os.path.exists(FAV_ASSETS_FILE):
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT"]
    try:
        with open(FAV_ASSETS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return list(data) if isinstance(data, list) else []
    except Exception:
        return []


def save_favorites(assets: list[str]) -> None:
    with open(FAV_ASSETS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(assets), f, indent=2, ensure_ascii=False)


def load_env_models() -> Dict[str, str]:
    """从 backend/.env 读取 Brale 三个 Agent 的模型名。

    返回以 CSV 列名（BRALE_*_MODEL）为 key 的字典。
    优先级：BRALE_XXX_MODEL > LLM_MODEL > AGENT_MODEL（兜底）。
    """
    models: Dict[str, str] = {
        "BRALE_INDICATOR_MODEL": "",
        "BRALE_STRUCTURE_MODEL": "",
        "BRALE_MECHANICS_MODEL": "",
    }
    llm_model = ""
    agent_model_fallback = ""
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                if line.startswith("LLM_MODEL="):
                    llm_model = line.split("=", 1)[1].strip()

                elif line.startswith("BRALE_INDICATOR_MODEL="):
                    models["BRALE_INDICATOR_MODEL"] = line.split("=", 1)[1].strip()
                elif line.startswith("BRALE_STRUCTURE_MODEL="):
                    models["BRALE_STRUCTURE_MODEL"] = line.split("=", 1)[1].strip()
                elif line.startswith("BRALE_MECHANICS_MODEL="):
                    models["BRALE_MECHANICS_MODEL"] = line.split("=", 1)[1].strip()

                elif line.startswith("AGENT_MODEL="):
                    agent_model_fallback = line.split("=", 1)[1].strip()

    except FileNotFoundError:
        pass

    # 兜底：各 Agent 若未配置，依次回退到 LLM_MODEL → AGENT_MODEL
    for key in models:
        if not models[key]:
            models[key] = llm_model or agent_model_fallback

    return models


def get_presets_list() -> list[str]:
    if not os.path.exists(PRESETS_DIR):
        return []
    files = [f for f in os.listdir(PRESETS_DIR) if f.endswith(".json")]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(PRESETS_DIR, x)), reverse=True)
    return [f[:-5] for f in files]


def load_preset(name: str) -> list[dict[str, Any]]:
    path = os.path.join(PRESETS_DIR, f"{name}.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return list(data) if isinstance(data, list) else []


def save_preset(name: str, tasks: list[dict[str, Any]]) -> tuple[bool, str]:
    os.makedirs(PRESETS_DIR, exist_ok=True)

    safe_name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    if not safe_name:
        return False, "任务集名称为空或非法"

    path = os.path.join(PRESETS_DIR, f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)
    return True, safe_name


def delete_preset(name: str) -> None:
    path = os.path.join(PRESETS_DIR, f"{name}.json")
    if os.path.exists(path):
        os.remove(path)


# --- Daemon Helper Functions ---

def save_daemon_config(config: dict[str, Any]) -> None:
    with open(DAEMON_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def load_daemon_config() -> dict[str, Any]:
    if not os.path.exists(DAEMON_CONFIG_FILE):
        return {}
    try:
        with open(DAEMON_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_daemon_progress(progress: dict[str, Any]) -> None:
    # Atomic write pattern to avoid reading partial file
    temp_path = DAEMON_PROGRESS_FILE + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, DAEMON_PROGRESS_FILE)


def load_daemon_progress() -> dict[str, Any]:
    if not os.path.exists(DAEMON_PROGRESS_FILE):
        return {}
    try:
        with open(DAEMON_PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_daemon_status(status: dict[str, Any]) -> None:
    with open(DAEMON_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def load_daemon_status() -> dict[str, Any]:
    if not os.path.exists(DAEMON_STATUS_FILE):
        return {}
    try:
        with open(DAEMON_STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}
