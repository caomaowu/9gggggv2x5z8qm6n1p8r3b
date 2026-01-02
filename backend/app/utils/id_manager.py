import os
import json
import threading
from pathlib import Path
from typing import Optional

_manager_lock = threading.Lock()
_global_manager = None


class ResultIDManager:
    def __init__(self, store_path: Optional[str] = None):
        base_path = store_path or os.environ.get("QUANTAGENT_ID_STORE")
        if not base_path:
            base_path = str(Path("data") / "global_id_counter.json")
        self.store_path = Path(base_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read_counter(self) -> int:
        if not self.store_path.exists():
            return 0
        try:
            with self.store_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return int(data.get("counter", 0))
        except Exception:
            return 0

    def _write_counter(self, value: int) -> None:
        tmp_path = self.store_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump({"counter": value}, f)
        os.replace(tmp_path, self.store_path)

    def get_next_id(self, prefix: str = "A", width: int = 4) -> str:
        with self._lock:
            current = self._read_counter()
            next_value = current + 1
            num_str = str(next_value)
            if len(num_str) < width:
                num_str = num_str.zfill(width)
            result_id = f"{prefix}{num_str}"
            self._write_counter(next_value)
            return result_id

    def peek_last_id(self, prefix: str = "A", width: int = 4) -> str:
        with self._lock:
            current = self._read_counter()
            if current <= 0:
                return f"{prefix}{'0'.zfill(width)}"
            num_str = str(current)
            if len(num_str) < width:
                num_str = num_str.zfill(width)
            return f"{prefix}{num_str}"


def get_result_id_manager() -> ResultIDManager:
    global _global_manager
    with _manager_lock:
        if _global_manager is None:
            _global_manager = ResultIDManager()
        return _global_manager

