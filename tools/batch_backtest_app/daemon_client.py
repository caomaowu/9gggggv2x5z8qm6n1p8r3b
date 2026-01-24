import os
import subprocess
import sys
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from batch_backtest_app import queue_manager


def _tools_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


DAEMON_SCRIPT = os.path.join(_tools_dir(), "batch_backtest_app", "batch_backtest_daemon.py")


def save_daemon_config(config: Dict[str, Any]) -> None:
    config_file = os.path.join(_tools_dir(), "data", "daemon_config.json")
    current_config = {}
    
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                current_config = json.load(f)
        except Exception:
            pass
            
    current_config.update(config)
    
    try:
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(current_config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def start_daemon(config: Optional[Dict[str, Any]] = None) -> tuple[bool, str]:
    if queue_manager.is_daemon_running():
        return False, "守护进程已在运行中"

    if config:
        save_daemon_config(config)

    try:
        python_exe = sys.executable

        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(
                [python_exe, DAEMON_SCRIPT],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
        else:
            subprocess.Popen(
                [python_exe, DAEMON_SCRIPT],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )

        import time
        time.sleep(1)

        if queue_manager.is_daemon_running():
            return True, "守护进程启动成功"
        else:
            return False, "守护进程启动失败（请检查日志）"

    except Exception as e:
        return False, f"启动失败: {str(e)}"


def stop_daemon() -> tuple[bool, str]:
    if not queue_manager.is_daemon_running():
        return False, "守护进程未运行"

    try:
        success = queue_manager.stop_daemon()
        if success:
            return True, "守护进程已停止"
        else:
            return False, "停止失败（进程可能已不存在）"
    except Exception as e:
        return False, f"停止失败: {str(e)}"


def is_daemon_running() -> bool:
    return queue_manager.is_daemon_running()


def add_tasks_to_queue(tasks: List[Dict[str, Any]], batch_name: Optional[str] = None) -> tuple[bool, str, int]:
    if not tasks:
        return False, "任务列表为空", 0

    try:
        added_count = queue_manager.add_tasks_to_queue(tasks, batch_name)
        return True, f"成功添加 {added_count} 个任务到队列", added_count
    except Exception as e:
        return False, f"添加失败: {str(e)}", 0


def get_queue_status() -> Dict[str, Any]:
    queue_info = queue_manager.get_queue_info()
    progress = queue_manager.load_progress()

    return {
        "daemon_running": queue_manager.is_daemon_running(),
        "queue_size": queue_info.get("queue_size", 0),
        "total_tasks_in_queue": queue_info.get("total_tasks_in_queue", 0),
        "batches": queue_info.get("batches", []),
        "progress": progress,
    }


def get_progress() -> Dict[str, Any]:
    progress = queue_manager.load_progress()

    if progress.get("is_running"):
        last_update = progress.get("last_update")
        if last_update:
            try:
                last_time = datetime.fromisoformat(last_update)
                delta = (datetime.now() - last_time).total_seconds()
                if delta > 120:
                    progress["is_running"] = False
                    progress["status"] = "超时（守护进程可能已停止）"
                else:
                    progress["status"] = "运行中"
            except Exception:
                progress["status"] = "运行中"
        else:
            progress["status"] = "运行中"
    else:
        progress["status"] = "空闲"

    total_valid = progress.get("stats_wins", 0) + progress.get("stats_losses", 0)
    win_rate = (progress.get("stats_wins", 0) / total_valid * 100.0) if total_valid > 0 else 0.0
    progress["win_rate"] = win_rate

    if progress.get("start_time"):
        try:
            start_time = datetime.fromisoformat(progress["start_time"])
            elapsed = (datetime.now() - start_time).total_seconds()
            progress["elapsed_seconds"] = elapsed
            progress["elapsed_formatted"] = format_duration(elapsed)
        except Exception:
            progress["elapsed_seconds"] = 0
            progress["elapsed_formatted"] = "未知"

    return progress


def clear_queue() -> tuple[bool, str, int]:
    try:
        count = queue_manager.clear_queue()
        return True, f"已清空队列（移除 {count} 个任务）", count
    except Exception as e:
        return False, f"清空失败: {str(e)}", 0


def get_daemon_status() -> Dict[str, Any]:
    status = queue_manager.load_status()
    progress = queue_manager.load_progress()
    queue_info = queue_manager.get_queue_info()

    return {
        "is_running": queue_manager.is_daemon_running(),
        "pid": status.get("pid"),
        "start_time": status.get("start_time"),
        "last_heartbeat": status.get("last_heartbeat"),
        "progress": progress,
        "queue_size": queue_info.get("queue_size", 0),
        "queue_batches": queue_info.get("batches", []),
    }


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)} 秒"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes} 分 {secs} 秒"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} 小时 {minutes} 分"
