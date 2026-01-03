import os
import json
import threading
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

_manager_lock = threading.Lock()
_global_manager = None


class ResultIDManager:
    """
    ID Manager for generating unique result IDs.
    Format: R-{AXXX}-{YYMMDD}-{HHMM}
    Example: R-A001-240102-1430
    
    The counter AXXX resets daily.
    """
    def __init__(self, store_path: Optional[str] = None):
        base_path = store_path or os.environ.get("QUANTAGENT_ID_STORE")
        if not base_path:
            base_path = str(Path("data") / "daily_id_counter.json")
        self.store_path = Path(base_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read_state(self) -> Dict:
        if not self.store_path.exists():
            return {"date": "", "counter": 0}
        try:
            with self.store_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"date": "", "counter": 0}

    def _write_state(self, state: Dict) -> None:
        tmp_path = self.store_path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp_path, self.store_path)

    def get_next_id(self, asset: str = None, timeframe: str = None) -> str:
        """
        Generate the next ID in format R-{AXXX}-{YYMMDD}-{HHMM}-{ASSET}-{TF}
        Example: R-A001-240102-1430-BTC-1H
        """
        with self._lock:
            now = datetime.now()
            current_date_str = now.strftime("%y%m%d")  # YYMMDD
            time_str = now.strftime("%H%M")           # HHMM
            
            state = self._read_state()
            last_date = state.get("date", "")
            current_counter = int(state.get("counter", 0))
            
            # Reset counter if date changed
            if last_date != current_date_str:
                current_counter = 0
                last_date = current_date_str
            
            next_counter = current_counter + 1
            
            # Format: AXXX (e.g., A001, A002...)
            # We use 'A' as a fixed prefix for the sequence part as requested
            seq_str = f"A{str(next_counter).zfill(3)}"
            
            # Construct base ID: R-{AXXX}-{YYMMDD}-{HHMM}
            result_id = f"R-{seq_str}-{current_date_str}-{time_str}"
            
            # Add Asset and Timeframe suffix if provided
            if asset:
                # Clean asset name (remove -USDT etc if needed, but keeping it simple usually better)
                # Just replace special chars to be safe for filenames
                safe_asset = asset.replace("/", "").replace("\\", "").upper()
                result_id += f"-{safe_asset}"
            
            if timeframe:
                safe_tf = timeframe.upper()
                result_id += f"-{safe_tf}"
            
            # Save state
            self._write_state({"date": current_date_str, "counter": next_counter})
            
            return result_id

    def peek_current_counter(self) -> int:
        """Helper to check current counter value without incrementing"""
        with self._lock:
            state = self._read_state()
            return int(state.get("counter", 0))


def get_result_id_manager() -> ResultIDManager:
    global _global_manager
    with _manager_lock:
        if _global_manager is None:
            _global_manager = ResultIDManager()
        return _global_manager

