from pydantic import BaseModel
from typing import Optional, Dict, Any

class DualModelConfig(BaseModel):
    dual_model: bool = False
    model_1: Optional[str] = None
    model_2: Optional[str] = None

class AnalyzeRequest(BaseModel):
    asset: str
    timeframe: str
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
    dual_model_config: Optional[DualModelConfig] = None
