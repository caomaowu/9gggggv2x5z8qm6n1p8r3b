import json
import os
import re
from typing import Any, Tuple


def _tools_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _repo_root() -> str:
    return os.path.dirname(_tools_dir())


FAV_ASSETS_FILE = os.path.join(_tools_dir(), "data", "favorite_assets.json")
PRESETS_DIR = os.path.join(_tools_dir(), "data", "task_presets")
ENV_PATH = os.path.join(_repo_root(), "backend", ".env")


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


def load_env_models() -> Tuple[str, str]:
    agent_model = ""
    graph_model = ""
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("AGENT_MODEL="):
                    agent_model = line.split("=", 1)[1].strip()
                elif line.startswith("GRAPH_MODEL="):
                    graph_model = line.split("=", 1)[1].strip()
        return agent_model, graph_model
    except FileNotFoundError:
        return "", ""
    except Exception:
        return agent_model, graph_model


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

