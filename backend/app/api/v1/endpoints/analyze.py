from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.models.schemas.analyze import AnalyzeRequest
from app.services.market_data import MarketDataService
from app.services.trading_engine import TradingEngine
from app.core.progress import update_analysis_progress
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

def get_market_service():
    return MarketDataService()

def get_trading_engine():
    # In a real app, this might be a singleton or cached
    return TradingEngine()

@router.post("/")
async def analyze_market(
    request: AnalyzeRequest,
    market_service: MarketDataService = Depends(get_market_service),
    # trading_engine: TradingEngine = Depends(get_trading_engine) # Instantiating per request for config flexibility
):
    try:
        update_analysis_progress("start", 0, f"Starting analysis for {request.asset}")
        
        logger.info(f"Fetching market data for {request.asset} ({request.timeframe})...")
        update_analysis_progress("fetching_data", 10, "Fetching market data...")
        
        # Determine start/end time based on request
        # (Simplified logic compared to original for brevity, but should be robust)
        start_dt_str = None
        end_dt_str = None
        
        if request.data_method == "date_range":
             if request.start_date:
                 start_dt_str = f"{request.start_date} {request.start_time}:00"
             if request.end_date:
                 end_dt_str = f"{request.end_date} {request.end_time}:00"
        elif request.data_method == "to_end" and request.end_date:
             end_dt_str = f"{request.end_date} {request.end_time}:00"

        df = market_service.get_ohlcv_data_enhanced(
            symbol=request.asset,
            timeframe=request.timeframe,
            limit=request.kline_count,
            method=request.data_method,
            start_date=start_dt_str,
            end_date=end_dt_str
        )
        
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail="No market data found")
            
        # 2. Configure Engine
        engine_config = {
            "decision_agent_version": request.ai_version,
            # Add other config overrides if needed
        }
        
        if request.dual_model_config and request.dual_model_config.dual_model:
            # Handle dual model config if needed
            pass
            
        trading_engine = TradingEngine(config=engine_config)
        
        # 3. Run Analysis
        logger.info(f"Starting AI analysis with engine config: {engine_config}")
        update_analysis_progress("analyzing", 30, "Running AI analysis...")
        result = await trading_engine.run_analysis(df, request.asset, request.timeframe)
        
        logger.info("Analysis completed successfully")
        update_analysis_progress("completed", 100, "Analysis completed")
        
        # Format response to match expected frontend structure if needed
        # For now return raw result
        return result
        
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        update_analysis_progress("error", 0, f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
