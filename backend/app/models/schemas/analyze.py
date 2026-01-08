from pydantic import BaseModel
from typing import Optional, Union, List

class AnalyzeRequest(BaseModel):
    asset: str
    timeframe: Union[str, List[str]]
    data_source: str = "quant_api"
    data_method: str = "latest"
    kline_count: int = 100
    future_kline_count: int = 13
    
    start_date: Optional[str] = None
    start_time: Optional[str] = "00:00"
    end_date: Optional[str] = None
    end_time: Optional[str] = "23:59"
    use_current_time: bool = False
    
    ai_version: str = "constrained"
    
    # Multi-Timeframe Mode
    multi_timeframe_mode: bool = False
    timeframes: Optional[List[str]] = None
