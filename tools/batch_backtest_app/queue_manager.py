import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


def _tools_dir() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


QUEUE_FILE = os.path.join(_tools_dir(), "data", "batch_backtest_queue.json")
PROGRESS_FILE = os.path.join(_tools_dir(), "data", "batch_backtest_progress.json")
STATUS_FILE = os.path.join(_tools_dir(), "data", "batch_backtest_status.json")
LOCK_FILE = os.path.join(_tools_dir(), "data", "batch_backtest.lock")


class FileLock:
    def __init__(self, lock_file: str, timeout: float = 10.0):
        self.lock_file = lock_file
        self.timeout = timeout
        self.locked = False

    def acquire(self) -> bool:
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            try:
                fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                self.locked = True
                return True
            except FileExistsError:
                time.sleep(0.1)
        return False

    def release(self) -> None:
        if self.locked and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
            except Exception:
                pass
        self.locked = False

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError(f"无法获取文件锁: {self.lock_file}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def load_queue() -> List[Dict[str, Any]]:
    if not os.path.exists(QUEUE_FILE):
        return []
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_queue(queue: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def load_progress() -> Dict[str, Any]:
    if not os.path.exists(PROGRESS_FILE):
        return {
            "is_running": False,
            "current_task_id": None,
            "current_task_index": 0,
            "total_tasks": 0,
            "completed_count": 0,
            "failed_count": 0,
            "start_time": None,
            "last_update": None,
            "current_asset": None,
            "current_timeframe": None,
            "current_end_date": None,
            "current_end_time": None,
            "stats_wins": 0,
            "stats_losses": 0,
            "equity": None,
        }
    try:
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return load_progress()


def save_progress(progress: Dict[str, Any]) -> None:
    progress["last_update"] = datetime.now().isoformat()
    with FileLock(PROGRESS_FILE.replace(".json", ".lock"), timeout=5.0):
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)


def load_status() -> Dict[str, Any]:
    if not os.path.exists(STATUS_FILE):
        return {"pid": None, "start_time": None, "last_heartbeat": None}
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"pid": None, "start_time": None, "last_heartbeat": None}


def save_status(status: Dict[str, Any]) -> None:
    with FileLock(STATUS_FILE.replace(".json", ".lock"), timeout=5.0):
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2, ensure_ascii=False)


def is_daemon_running(timeout: int = 60) -> bool:
    status = load_status()
    pid = status.get("pid")
    if not pid:
        return False

    try:
        import psutil
        if psutil.pid_exists(pid):
            process = psutil.Process(pid)
            if process.is_running():
                heartbeat = status.get("last_heartbeat")
                if heartbeat:
                    try:
                        from datetime import datetime
                        last_time = datetime.fromisoformat(heartbeat)
                        if (datetime.now() - last_time).total_seconds() < timeout:
                            return True
                    except Exception:
                        pass
                return True
    except ImportError:
        pass
    except Exception:
        pass

    return False


def stop_daemon() -> bool:
    status = load_status()
    pid = status.get("pid")
    if not pid:
        return False

    try:
        import psutil
        if psutil.pid_exists(pid):
            process = psutil.Process(pid)
            process.terminate()
            try:
                process.wait(timeout=5)
            except Exception:
                process.kill()
            return True
    except Exception:
        pass

    return False


def add_tasks_to_queue(tasks: List[Dict[str, Any]], batch_name: Optional[str] = None) -> int:
    with FileLock(QUEUE_FILE.replace(".json", ".lock"), timeout=5.0):
        queue = load_queue()

        batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        for i, task in enumerate(tasks):
            task_copy = task.copy()
            task_copy["_batch_id"] = batch_id
            task_copy["_batch_name"] = batch_name or f"批次 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            task_copy["_batch_index"] = i
            task_copy["_queue_time"] = datetime.now().isoformat()
            queue.append(task_copy)

        save_queue(queue)
        return len(tasks)


def clear_queue() -> int:
    with FileLock(QUEUE_FILE.replace(".json", ".lock"), timeout=5.0):
        queue = load_queue()
        count = len(queue)
        queue.clear()
        save_queue(queue)
        return count


def get_next_task() -> Optional[Dict[str, Any]]:
    with FileLock(QUEUE_FILE.replace(".json", ".lock"), timeout=5.0):
        queue = load_queue()
        if not queue:
            return None
        task = queue.pop(0)
        save_queue(queue)
        return task


def get_queue_info() -> Dict[str, Any]:
    queue = load_queue()
    progress = load_progress()

    if not queue:
        return {
            "queue_size": 0,
            "total_tasks_in_queue": 0,
            "batches": [],
        }

    batches: Dict[str, Any] = {}
    for task in queue:
        batch_id = task.get("_batch_id", "unknown")
        batch_name = task.get("_batch_name", "未知批次")
        if batch_id not in batches:
            batches[batch_id] = {
                "name": batch_name,
                "count": 0,
                "first_task_time": task.get("_queue_time"),
            }
        batches[batch_id]["count"] += 1

    return {
        "queue_size": len(queue),
        "total_tasks_in_queue": len(queue),
        "batches": [
            {
                "id": bid,
                "name": binfo["name"],
                "count": binfo["count"],
                "first_task_time": binfo["first_task_time"],
            }
            for bid, binfo in batches.items()
        ],
    }
