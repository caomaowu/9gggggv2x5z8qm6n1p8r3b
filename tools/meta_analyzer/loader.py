import os
import json
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

class DataLoader:
    def __init__(self, history_dir: str):
        self.history_dir = history_dir
        self.cases_cache = []

    def load_all_cases(self) -> pd.DataFrame:
        """
        扫描 history 目录，加载所有案例的元数据。
        如果数据量大，后续可以增加缓存机制。
        """
        cases = []
        
        if not os.path.exists(self.history_dir):
            return pd.DataFrame()

        # 遍历所有日期目录
        for date_folder in os.listdir(self.history_dir):
            date_path = os.path.join(self.history_dir, date_folder)
            if not os.path.isdir(date_path):
                continue
            
            for filename in os.listdir(date_path):
                if not filename.endswith(".json"):
                    continue
                
                file_path = os.path.join(date_path, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        # 只读取前几个字节或部分解析以提高速度？
                        # 这里为了简单，读取全部但只提取元数据
                        data = json.load(f)
                        
                        # 提取决策
                        decision_data = data.get("decision", {})
                        action = decision_data.get("action", "HOLD")
                        if not action:
                            # 尝试解析 final_trade_decision 字符串
                            ftd = data.get("final_trade_decision", "")
                            if isinstance(ftd, str) and "LONG" in ftd:
                                action = "LONG"
                            elif isinstance(ftd, str) and "SHORT" in ftd:
                                action = "SHORT"
                        
                        # 简单的结果计算 (如果有未来数据)
                        pnl_status = "Unknown"
                        max_profit = 0.0
                        max_drawdown = 0.0
                        
                        future_kline = data.get("future_kline_data", [])
                        entry_price = float(data.get("latest_price", 0) or decision_data.get("entry_point", 0) or 0)
                        
                        if entry_price > 0 and future_kline and action in ["LONG", "SHORT"]:
                            # 计算未来数据的最高/最低价
                            highs = [k.get("high", 0) for k in future_kline]
                            lows = [k.get("low", 0) for k in future_kline]
                            
                            if action == "LONG":
                                max_price = max(highs) if highs else entry_price
                                min_price = min(lows) if lows else entry_price
                                max_profit = (max_price - entry_price) / entry_price * 100
                                max_drawdown = (min_price - entry_price) / entry_price * 100
                            elif action == "SHORT":
                                max_price = max(highs) if highs else entry_price
                                min_price = min(lows) if lows else entry_price
                                max_profit = (entry_price - min_price) / entry_price * 100
                                max_drawdown = (entry_price - max_price) / entry_price * 100
                            
                            # 简单判定状态
                            if max_profit > 2.0:  # 假设 > 2% 算大赚
                                pnl_status = "Win"
                            elif max_drawdown < -2.0: # 假设 < -2% 算大亏
                                pnl_status = "Loss"
                            else:
                                pnl_status = "Choppy"

                        cases.append({
                            "result_id": data.get("result_id", filename.replace(".json", "")),
                            "timestamp": data.get("analysis_time_display", date_folder),
                            "asset": data.get("asset", "Unknown"),
                            "timeframe": data.get("timeframe", "4h"),
                            "action": action,
                            "pnl_status": pnl_status,
                            "max_profit": round(max_profit, 2),
                            "max_drawdown": round(max_drawdown, 2),
                            "file_path": file_path
                        })
                        
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
                    continue

        self.cases_cache = cases
        return pd.DataFrame(cases)

    def get_case_detail(self, file_path: str) -> Dict:
        """加载单个案例的完整数据"""
        if not os.path.exists(file_path):
            return {}
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
