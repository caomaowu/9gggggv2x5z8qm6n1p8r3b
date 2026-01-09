from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage


class IndicatorAgentState(TypedDict):
    """State type for the Indicator Agent including messages, input data, and analysis result."""

    kline_data: Annotated[
        dict, "OHLCV dictionary used for computing technical indicators"
    ]
    time_frame: Annotated[str, "time period for k line data provided"]
    stock_name: Annotated[str, "stock name for prompt"]  # 修复：类型从 dict 改为 str，与实际使用保持一致

    # Indicator Agent Tools output values (explicitly added per indicator)
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

    # Pattern Agent
    pattern_image: Annotated[
        str, "Base64-encoded K-line chart for pattern recognition agent use"
    ]
    pattern_image_filename: Annotated[
        str, "Local file path to saved K-line chart image"
    ]
    pattern_image_description: Annotated[
        str, "Brief description of the generated K-line image"
    ]
    pattern_report: Annotated[
        str, "Final pattern agent summary report to be used by downstream agents"
    ]
    pattern_images: Annotated[
        dict, "Dictionary of base64-encoded K-line charts for multi-timeframe pattern recognition"
    ]

    # Trend Agent
    trend_image: Annotated[
        str,
        "Base64-encoded trend-annotated candlestick (K-line) chart for trend recognition agent use",
    ]
    trend_image_filename: Annotated[
        str, "Local file path to saved trendline-enhanced K-line chart image"
    ]
    trend_image_description: Annotated[
        str,
        "Brief description of the chart, including presence of support/resistance lines and visual characteristics",
    ]
    trend_report: Annotated[
        str,
        "Final trend analysis summary, describing structure, directional bias, and technical observations for downstream agents",
    ]
    trend_images: Annotated[
        dict, "Dictionary of base64-encoded trend charts for multi-timeframe trend analysis"
    ]

    # Price information (哈雷酱添加：确保价格信息在状态中传递)
    latest_price: Annotated[float, "Latest trading price from kline data"]
    price_info: Annotated[str, "Formatted price information string"]

    # Final analysis and messaging context
    analysis_results: Annotated[str, "Computed result of the analysis or decision"]
    messages: Annotated[
        List[BaseMessage], "List of chat messages used in LLM prompt construction"
    ]
    decision_prompt: Annotated[str, "decision prompt for reflection"]
    final_trade_decision: Annotated[
        str, "Final BUY or SELL decision made after analyzing indicators"
    ]
    
    # Multi-timeframe support
    multi_timeframe_mode: Annotated[bool, "Flag indicating if multi-timeframe analysis is active"]
    timeframes: Annotated[List[str], "List of timeframes being analyzed"]
