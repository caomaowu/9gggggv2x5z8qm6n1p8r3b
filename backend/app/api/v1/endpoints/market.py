from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from app.services.market_data import MarketDataService

router = APIRouter()

def get_market_service():
    return MarketDataService()

@router.get("/health")
def check_health(service: MarketDataService = Depends(get_market_service)):
    return service.check_health()

@router.get("/ohlcv/{symbol}")
def get_ohlcv(
    symbol: str, 
    timeframe: str = "1h", 
    limit: int = 100,
    service: MarketDataService = Depends(get_market_service)
):
    df = service.get_ohlcv_data(symbol, timeframe, limit)
    if df is None:
        raise HTTPException(status_code=404, detail="Data not found")
    
    # Convert DataFrame to list of dicts for JSON response
    # Index is Date, so we reset index
    df_reset = df.reset_index()
    # Convert Timestamp to string
    df_reset['Date'] = df_reset['Date'].astype(str)
    return df_reset.to_dict(orient="records")

@router.get("/exchanges")
def get_exchanges(service: MarketDataService = Depends(get_market_service)):
    return service.get_exchanges()
