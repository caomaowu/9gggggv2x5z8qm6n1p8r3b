import mplfinance as mpf

font = {
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.weight": "normal",
    "font.size": 15,
}

my_color_style = mpf.make_mpf_style(
    marketcolors=mpf.make_marketcolors(
        up="#A02128",  # color for bullish candles (Red for Up)
        down="#006340",  # color for bearish candles (Green for Down)
        edge="none",  # use candle fill color for edge
        wick="black",  # color of the wicks
        volume="in",  # default volume coloring
    ),
    gridstyle="-",
    facecolor="white",  # background color
    rc=font,
)

def get_trading_style():
    """获取交易图表样式（向后兼容）"""
    return my_color_style
