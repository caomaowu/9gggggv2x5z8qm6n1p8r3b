from typing import Annotated, Any, List, Optional, TypedDict

from langchain_core.messages import BaseMessage


class IndicatorAgentState(TypedDict):
    """State type for the Indicator Agent including messages, input data, and analysis result."""

    kline_data: Annotated[
        dict, "OHLCV dictionary used for computing technical indicators"
    ]
    multi_timeframe_data: Annotated[
        Optional[dict], "Dict[str, DataFrame] for multi-timeframe mode"
    ]
    time_frame: Annotated[str, "time period for k line data provided"]
    stock_name: Annotated[str, "stock name for prompt"]

    # --- Legacy fields (kept for backward compat) ---
    rsi: Annotated[List[float], "Relative Strength Index values"]
    macd: Annotated[List[float], "MACD line values"]
    macd_signal: Annotated[List[float], "MACD signal line values"]
    macd_hist: Annotated[List[float], "MACD histogram values"]
    stoch_k: Annotated[List[float], "Stochastic Oscillator %K values"]
    stoch_d: Annotated[List[float], "Stochastic Oscillator %D values"]
    roc: Annotated[List[float], "Rate of Change values"]
    willr: Annotated[List[float], "Williams %R values"]
    indicator_report: Annotated[
        str, "Final indicator agent summary report to be used by downstream agents"
    ]
    pattern_image: Annotated[
        str, "Base64-encoded K-line chart for pattern recognition agent use"
    ]
    pattern_image_filename: Annotated[str, "Local file path to saved K-line chart image"]
    pattern_image_description: Annotated[str, "Brief description of the generated K-line image"]
    pattern_report: Annotated[
        str, "Final pattern agent summary report to be used by downstream agents"
    ]
    pattern_images: Annotated[
        dict, "Dictionary of base64-encoded K-line charts for multi-timeframe pattern recognition"
    ]
    trend_image: Annotated[
        str, "Base64-encoded trend-annotated candlestick chart for trend recognition agent use"
    ]
    trend_image_filename: Annotated[str, "Local file path to saved trendline-enhanced K-line chart image"]
    trend_image_description: Annotated[
        str, "Brief description of the chart, including support/resistance lines and visual characteristics"
    ]
    trend_report: Annotated[
        str, "Final trend analysis summary for downstream agents"
    ]
    trend_images: Annotated[
        dict, "Dictionary of base64-encoded trend charts for multi-timeframe trend analysis"
    ]

    # --- Brale compressed data ---
    indicator_compressed: Annotated[
        Optional[dict], "Compressed indicator JSON from indicator_compress"
    ]
    structure_compressed: Annotated[
        Optional[dict], "Compressed structure JSON from structure_compress"
    ]
    mechanics_compressed: Annotated[
        Optional[dict], "Compressed mechanics JSON from mechanics_compress"
    ]

    # --- Brale agent summaries ---
    indicator_summary: Annotated[
        Optional[dict], "IndicatorSummary from brale_indicator_agent"
    ]
    structure_summary: Annotated[
        Optional[dict], "StructureSummary from brale_structure_agent"
    ]
    mechanics_summary: Annotated[
        Optional[dict], "MechanicsSummary from brale_mechanics_agent"
    ]

    # --- Fusion ---
    fusion_result: Annotated[
        Optional[dict], "Consensus fusion result {direction, score, confidence, ...}"
    ]

    # --- Derivative data (for mechanics compress) ---
    derivative_data: Annotated[
        Optional[dict], "Raw derivative market data from MarketDataService"
    ]

    # --- Price information ---
    latest_price: Annotated[float, "Latest trading price from kline data"]
    price_info: Annotated[str, "Formatted price information string"]

    # --- Final analysis ---
    analysis_results: Annotated[str, "Computed result of the analysis or decision"]
    messages: Annotated[
        List[BaseMessage], "List of chat messages used in LLM prompt construction"
    ]
    decision_prompt: Annotated[str, "decision prompt for reflection"]
    final_trade_decision: Annotated[
        str, "Final BUY or SELL decision made after analyzing indicators"
    ]

    # --- Multi-timeframe ---
    multi_timeframe_mode: Annotated[bool, "Flag indicating if multi-timeframe analysis is active"]
    timeframes: Annotated[List[str], "List of timeframes being analyzed"]
