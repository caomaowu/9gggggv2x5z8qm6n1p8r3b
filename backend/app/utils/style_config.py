"""
Style Configuration - 图表样式配置
从color_style.py重命名并扩展的样式配置模块
作者：哈雷酱（傲娇大小姐工程师）
"""

import mplfinance as mpf
import matplotlib.pyplot as plt


def get_compatible_font_list():
    """
    获取跨平台兼容的字体列表
    优先使用中文字体，如果没有则回退到英文
    """
    # Windows 常用字体
    windows_fonts = ['Microsoft YaHei', 'SimHei', 'SimSun', 'KaiTi']
    
    # Linux 常用字体 (涵盖常见发行版)
    linux_fonts = [
        'Noto Sans CJK SC', 'Noto Sans CJK',   # Google/Adobe 开源字体
        'WenQuanYi Micro Hei',                 # 文泉驿微米黑
        'WenQuanYi Zen Hei',                   # 文泉驿正黑
        'Droid Sans Fallback',                 # 旧版Linux默认
        'Source Han Sans CN',                  # 思源黑体
        'Source Han Sans SC'
    ]
    
    # Mac 常用字体
    mac_fonts = ['PingFang SC', 'Heiti SC', 'STHeiti', 'Arial Unicode MS']
    
    # 英文/通用保底
    fallback_fonts = ['Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif']
    
    # 组合列表：优先把所有可能的中文字体都放进去
    # Matplotlib 会按顺序查找，找到第一个可用的就停止
    return windows_fonts + linux_fonts + mac_fonts + fallback_fonts


def get_trading_style():
    """
    获取交易图表样式配置

    哼哼！本小姐的图表样式可是最专业的！
    """
    return {
        'font.size': 10,
        'axes.titlesize': 12,
        'axes.labelsize': 10,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'legend.fontsize': 9,
        'figure.titlesize': 14,
        'lines.linewidth': 1.5,
        'lines.markersize': 6,
        'axes.grid': True,
        'grid.alpha': 0.3,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'font.sans-serif': get_compatible_font_list(),
        'axes.unicode_minus': False,
    }


def get_market_colors():
    """获取市场颜色配置"""
    return mpf.make_marketcolors(
        up='red',      # 上涨红色（中国股市习惯）
        down='green',  # 下跌绿色
        edge='black',
        wick='black',
        volume='in',
        ohlc='i'       # OHLCC柱状图
    )


def create_trading_style(name="harley_trading"):
    """
    创建自定义交易样式

    Args:
        name: 样式名称

    Returns:
        mplfinance样式对象
    """
    market_colors = get_market_colors()
    base_style_rc = get_trading_style()
    
    # 兼容性处理：检查可用的 matplotlib 样式
    base_mpl_style = 'seaborn'
    if base_mpl_style not in plt.style.available:
        # 尝试查找替代的 seaborn 样式
        seaborn_styles = [s for s in plt.style.available if 'seaborn' in s]
        if seaborn_styles:
            base_mpl_style = seaborn_styles[0]
        else:
            base_mpl_style = 'ggplot' # 保底方案

    return mpf.make_mpf_style(
        base_mpl_style=base_mpl_style,
        marketcolors=market_colors,
        rc=base_style_rc,
        y_on_right=True
    )


# 哈雷酱特制样式！
HARLEY_STYLE = create_trading_style()


def get_chart_config(chart_type="candle"):
    """
    获取图表配置参数

    Args:
        chart_type: 图表类型 ('candle', 'line', 'ohlc')

    Returns:
        图表配置字典
    """
    config = {
        'type': chart_type,
        'style': HARLEY_STYLE,
        'title': '',
        'ylabel': '',
        'volume': False,
        'figsize': (12, 8),
        'savefig': dict(dpi=100, bbox_inches='tight'),
        'warn_too_much_data': 1000
    }

    if chart_type == 'candle':
        config.update({
            'mav': (20, 50),  # 移动平均线
            'show_nontrading': False
        })

    return config


def apply_style_theme(fig, theme="professional"):
    """
    应用图表主题

    Args:
        fig: matplotlib图表对象
        theme: 主题名称
    """
    if theme == "professional":
        fig.patch.set_facecolor('white')
        fig.set_facecolor('white')
    elif theme == "dark":
        fig.patch.set_facecolor('#1e1e1e')
        fig.set_facecolor('#1e1e1e')
    elif theme == "harley":
        fig.patch.set_facecolor('#f0f8ff')  # 本小姐喜欢的淡蓝色！
        fig.set_facecolor('#f0f8ff')