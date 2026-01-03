import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class HistoryService:
    """
    Service for saving and retrieving analysis history.
    Stores results as JSON files in data/history/YYYY-MM-DD/
    """
    
    def __init__(self):
        self.base_dir = Path("data") / "history"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_date_from_id(self, result_id: str) -> Optional[str]:
        """
        Extract date (YYYY-MM-DD) from result_id (R-AXXX-YYMMDD-HHMM)
        """
        try:
            parts = result_id.split('-')
            if len(parts) >= 3:
                date_part = parts[2] # YYMMDD
                if len(date_part) == 6:
                    year = "20" + date_part[0:2]
                    month = date_part[2:4]
                    day = date_part[4:6]
                    return f"{year}-{month}-{day}"
        except Exception as e:
            logger.warning(f"Failed to parse date from result_id {result_id}: {e}")
        return None

    def save_result(self, result_id: str, data: Dict[str, Any]) -> str:
        """
        Save analysis result to JSON file.
        Returns the file path.
        """
        try:
            date_str = self._get_date_from_id(result_id)
            if not date_str:
                # Fallback to today if parsing fails
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            save_dir = self.base_dir / date_str
            save_dir.mkdir(parents=True, exist_ok=True)
            
            file_path = save_dir / f"{result_id}.json"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                
            logger.info(f"Saved analysis history to {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"Failed to save history for {result_id}: {e}")
            raise e

    def get_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve analysis result by ID.
        """
        try:
            date_str = self._get_date_from_id(result_id)
            
            # If we can parse the date, look in that specific folder
            if date_str:
                file_path = self.base_dir / date_str / f"{result_id}.json"
                if file_path.exists():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        return json.load(f)
            
            # Fallback: Search in all date folders if not found or date parse failed
            # This handles edge cases or if files were moved
            for date_dir in self.base_dir.iterdir():
                if date_dir.is_dir():
                    file_path = date_dir / f"{result_id}.json"
                    if file_path.exists():
                        with open(file_path, 'r', encoding='utf-8') as f:
                            return json.load(f)
                            
            logger.warning(f"History not found for {result_id}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve history for {result_id}: {e}")
            return None

    def get_history_list(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get list of recent analysis results.
        Returns metadata only (not full content).
        """
        history_list = []
        try:
            # Iterate all date directories, reverse sorted (newest first)
            date_dirs = sorted([d for d in self.base_dir.iterdir() if d.is_dir()], reverse=True)
            
            for date_dir in date_dirs:
                if len(history_list) >= limit:
                    break
                    
                # Iterate files in date dir
                files = sorted(date_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
                
                for file_path in files:
                    if len(history_list) >= limit:
                        break
                        
                    try:
                        # Read just enough to get metadata
                        # Or just rely on filename/stat
                        stat = file_path.stat()
                        result_id = file_path.stem
                        
                        history_list.append({
                            "result_id": result_id,
                            "date": date_dir.name,
                            "timestamp": stat.st_mtime,
                            "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                        })
                    except Exception:
                        continue
                        
            return history_list
            
        except Exception as e:
            logger.error(f"Failed to list history: {e}")
            return []

history_service = HistoryService()
