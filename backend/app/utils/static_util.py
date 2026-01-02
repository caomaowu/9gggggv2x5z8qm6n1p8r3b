import base64
import io

import matplotlib
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd

from .color_style import get_trading_style
from .graph_util import (
    fit_trendlines_high_low,
    fit_trendlines_single,
    get_line_points,
    split_line_into_segments,
)
from .file_manager import get_file_manager

matplotlib.use("Agg")

# 哈雷酱的性能监控系统！
from .performance import performance_monitor, monitor_image_generation

# 哈雷酱的智能文件管理器！
file_manager = get_file_manager()


@performance_monitor("K线图表生成")
def generate_kline_image(kline_data) -> dict:
    """
    Generate a candlestick (K-line) chart from OHLCV data, save it locally, and return a base64-encoded image.

    Args:
        kline_data (dict): Dictionary with keys including 'Datetime', 'Open', 'High', 'Low', 'Close'.

    Returns:
        dict: Dictionary containing base64-encoded image string and local file path.
    """
    # 哈雷酱的智能文件管理：生成绝对唯一的文件名！
    csv_filename, csv_path = file_manager.generate_unique_filename("record", ".csv")
    chart_filename, chart_path = file_manager.generate_unique_filename("kline_chart", ".png")

    df = pd.DataFrame(kline_data)
    # take recent 40
    df = df.tail(40)

    df.to_csv(csv_path, index=False, date_format="%Y-%m-%d %H:%M:%S")
    try:
        # df.index = pd.to_datetime(df["Datetime"])
        df.index = pd.to_datetime(df["Datetime"], format="%Y-%m-%d %H:%M:%S")

    except ValueError:
        print("ValueError at graph_util.py\n")

    # Save image locally
    fig, axlist = mpf.plot(
        df[["Open", "High", "Low", "Close"]],
        type="candle",
        style=get_trading_style(),
        figsize=(12, 6),
        returnfig=True,
        block=False,
    )
    axlist[0].set_ylabel("Price", fontweight="normal")
    axlist[0].set_xlabel("Datetime", fontweight="normal")

    fig.savefig(
        fname=chart_path,
        dpi=600,
        bbox_inches="tight",
        pad_inches=0.1,
    )
    plt.close(fig)
    # ---------- Encode to base64 -----------------
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=600, bbox_inches="tight", pad_inches=0.1)
    plt.close(fig)  # release memory

    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")

    return {
        "pattern_image": img_b64,
        "pattern_image_description": f"Candlestick chart saved as {chart_filename} and returned as base64 string.",
        "pattern_image_filename": chart_path,
    }


@performance_monitor("趋势线图表生成")
def generate_trend_image(kline_data) -> dict:
    """
    Generate a candlestick chart with trendlines from OHLCV data,
    save it locally with unique filename, and return a base64-encoded image.

    Returns:
        dict: base64 image and description
    """
    # 哈雷酱的智能文件管理：生成绝对唯一的文件名！
    chart_filename, chart_path = file_manager.generate_unique_filename("trend_graph", ".png")

    data = pd.DataFrame(kline_data)
    candles = data.iloc[-50:].copy()

    candles["Datetime"] = pd.to_datetime(candles["Datetime"])
    candles.set_index("Datetime", inplace=True)

    # Trendline fit functions assumed to be defined outside this scope
    support_coefs_c, resist_coefs_c = fit_trendlines_single(candles["Close"])
    support_coefs, resist_coefs = fit_trendlines_high_low(
        candles["High"], candles["Low"], candles["Close"]
    )

    # Trendline values
    support_line_c = support_coefs_c[0] * np.arange(len(candles)) + support_coefs_c[1]
    resist_line_c = resist_coefs_c[0] * np.arange(len(candles)) + resist_coefs_c[1]
    support_line = support_coefs[0] * np.arange(len(candles)) + support_coefs[1]
    resist_line = resist_coefs[0] * np.arange(len(candles)) + resist_coefs[1]

    # Convert to time-anchored coordinates
    s_seq = get_line_points(candles, support_line)
    r_seq = get_line_points(candles, resist_line)
    s_seq2 = get_line_points(candles, support_line_c)
    r_seq2 = get_line_points(candles, resist_line_c)

    s_segments = split_line_into_segments(s_seq)
    r_segments = split_line_into_segments(r_seq)
    s2_segments = split_line_into_segments(s_seq2)
    r2_segments = split_line_into_segments(r_seq2)

    all_segments = s_segments + r_segments + s2_segments + r2_segments
    colors = (
        ["white"] * len(s_segments)
        + ["white"] * len(r_segments)
        + ["blue"] * len(s2_segments)
        + ["red"] * len(r2_segments)
    )

    # Create addplot lines for close-based support/resistance
    apds = [
        mpf.make_addplot(support_line_c, color="blue", width=1, label="Close Support"),
        mpf.make_addplot(resist_line_c, color="red", width=1, label="Close Resistance"),
    ]

    # Generate figure with legend and save locally
    fig, axlist = mpf.plot(
        candles,
        type="candle",
        style=get_trading_style(),
        addplot=apds,
        alines=dict(alines=all_segments, colors=colors, linewidths=1),
        returnfig=True,
        figsize=(12, 6),
        block=False,
    )

    axlist[0].set_ylabel("Price", fontweight="normal")
    axlist[0].set_xlabel("Datetime", fontweight="normal")

    # save fig locally
    fig.savefig(
        chart_path, format="png", dpi=600, bbox_inches="tight", pad_inches=0.1
    )
    plt.close(fig)

    # Add legend manually
    axlist[0].legend(loc="upper left")

    # Save to base64
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)

    return {
        "trend_image": img_b64,
        "trend_image_description": f"Trend-enhanced candlestick chart saved as {chart_filename} with support/resistance lines.",
        "trend_image_filename": chart_path,
    }
