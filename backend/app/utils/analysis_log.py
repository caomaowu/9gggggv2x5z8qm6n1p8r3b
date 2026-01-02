import csv
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional
import time

_log_lock = threading.Lock()
_recent: dict = {}


class AnalysisLogger:
    def __init__(self, file_path: Optional[str] = None):
        path = file_path or str(Path("data") / "analysis_log.csv")
        self.file_path = Path(path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def append_start_log(self, result_id: str, asset: str, timeframe: str, started_at: Optional[str] = None) -> None:
        ts = started_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        with _log_lock:
            new_file = not self.file_path.exists()
            with self.file_path.open("a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if new_file:
                    writer.writerow(["result_id", "asset", "timeframe", "started_at"])
                writer.writerow([result_id, asset, timeframe, ts])

    def append_start_log_once(self, result_id: str, asset: str, timeframe: str, started_at: Optional[str] = None, ttl_seconds: float = 2.0) -> None:
        now = time.time()
        key = f"{asset}|{timeframe}"
        prev = _recent.get(key)
        if prev and (now - prev) < ttl_seconds:
            return
        _recent[key] = now
        self.append_start_log(result_id, asset, timeframe, started_at)


_global_logger: Optional[AnalysisLogger] = None


def get_analysis_logger() -> AnalysisLogger:
    global _global_logger
    if _global_logger is None:
        _global_logger = AnalysisLogger()
    return _global_logger

