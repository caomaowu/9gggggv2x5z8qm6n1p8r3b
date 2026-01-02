"""
Chart Generator - 图表生成工具
从static_util.py中分离出来的图表生成功能
作者：哈雷酱（傲娇大小姐工程师）
"""

import base64
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
from typing import Optional

from .performance import performance_monitor, monitor_image_generation
from .style_config import get_trading_style


class ChartGenerator:
    """
    图表生成器

    哼哼！本小姐把图表功能单独分离出来，
    现在代码职责更加清晰了！
    """

    def __init__(self):
        """初始化图表生成器"""
        self.style = get_trading_style()

    @performance_monitor("K线图生成")
    def generate_kline_chart(self, data: pd.DataFrame, title: str = "K线图",
                           save_path: Optional[str] = None) -> str:
        """
        生成K线图表

        Args:
            data: OHLCV数据
            title: 图表标题
            save_path: 保存路径（可选）

        Returns:
            Base64编码的图片字符串
        """
        try:
            with monitor_image_generation("K线图"):
                # 确保数据格式正确
                if not all(col in data.columns for col in ['Open', 'High', 'Low', 'Close']):
                    raise ValueError("数据缺少必要的OHLC列")

                # 设置mplfinance样式
                mc = mpf.make_marketcolors(up='red', down='green', edge='black',
                                         wick='black', volume='in')
                s = mpf.make_mpf_style(base_mpl_style='seaborn', marketcolors=mc, rc=self.style)

                # 创建图表
                fig, axes = mpf.plot(
                    data,
                    type='candle',
                    style=s,
                    title=title,
                    ylabel='价格',
                    volume=True,
                    figsize=(12, 8),
                    returnfig=True,
                    warn_too_much_data=len(data) > 1000
                )

                # 优化布局
                fig.tight_layout()

                # 转换为base64
                buffer = io.BytesIO()
                fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
                buffer.seek(0)
                image_base64 = base64.b64encode(buffer.getvalue()).decode()
                plt.close(fig)

                # 保存到文件（如果指定了路径）
                if save_path:
                    with open(save_path, 'wb') as f:
                        f.write(base64.b64decode(image_base64))

                return image_base64

        except Exception as e:
            raise ValueError(f"K线图生成失败: {str(e)}")

    @performance_monitor("趋势图生成")
    def generate_trend_chart(self, data: pd.DataFrame, indicators: dict,
                           title: str = "技术指标分析图", save_path: Optional[str] = None) -> str:
        """
        生成技术指标趋势图

        Args:
            data: OHLCV数据
            indicators: 技术指标数据
            title: 图表标题
            save_path: 保存路径（可选）

        Returns:
            Base64编码的图片字符串
        """
        try:
            with monitor_image_generation("趋势图"):
                fig, axes = plt.subplots(3, 1, figsize=(12, 10))
                fig.suptitle(title, fontsize=16)

                # 第一个子图：价格和移动平均线
                ax1 = axes[0]
                ax1.plot(data.index, data['Close'], label='收盘价', linewidth=2)

                # 添加移动平均线
                if len(data) >= 20:
                    ma20 = data['Close'].rolling(window=20).mean()
                    ax1.plot(data.index, ma20, label='MA20', alpha=0.7)
                if len(data) >= 50:
                    ma50 = data['Close'].rolling(window=50).mean()
                    ax1.plot(data.index, ma50, label='MA50', alpha=0.7)

                ax1.set_title('价格走势')
                ax1.set_ylabel('价格')
                ax1.legend()
                ax1.grid(True, alpha=0.3)

                # 第二个子图：RSI
                ax2 = axes[1]
                if "rsi" in indicators:
                    rsi_values = indicators["rsi"]["rsi"]
                    rsi_length = min(len(rsi_values), len(data))
                    ax2.plot(data.index[-rsi_length:], rsi_values[-rsi_length:], label='RSI', color='purple')
                    ax2.axhline(y=70, color='red', linestyle='--', alpha=0.7, label='超买线')
                    ax2.axhline(y=30, color='green', linestyle='--', alpha=0.7, label='超卖线')
                    ax2.set_title('RSI指标')
                    ax2.set_ylabel('RSI')
                    ax2.set_ylim(0, 100)
                    ax2.legend()
                    ax2.grid(True, alpha=0.3)

                # 第三个子图：MACD
                ax3 = axes[2]
                if "macd" in indicators:
                    macd_data = indicators["macd"]
                    macd_length = min(len(macd_data["macd"]), len(data))

                    x_axis = data.index[-macd_length:]
                    ax3.plot(x_axis, macd_data["macd"][-macd_length:], label='MACD', linewidth=2)
                    ax3.plot(x_axis, macd_data["signal"][-macd_length:], label='Signal', linewidth=2)

                    # 柱状图
                    histogram = macd_data["histogram"][-macd_length:]
                    colors = ['red' if h < 0 else 'green' for h in histogram]
                    ax3.bar(x_axis, histogram, color=colors, alpha=0.6, label='Histogram')

                    ax3.set_title('MACD指标')
                    ax3.set_ylabel('MACD')
                    ax3.axhline(y=0, color='black', linestyle='-', alpha=0.3)
                    ax3.legend()
                    ax3.grid(True, alpha=0.3)

                plt.tight_layout()

                # 转换为base64
                buffer = io.BytesIO()
                fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
                buffer.seek(0)
                image_base64 = base64.b64encode(buffer.getvalue()).decode()
                plt.close(fig)

                # 保存到文件（如果指定了路径）
                if save_path:
                    with open(save_path, 'wb') as f:
                        f.write(base64.b64decode(image_base64))

                return image_base64

        except Exception as e:
            raise ValueError(f"趋势图生成失败: {str(e)}")

    @performance_monitor("成交量图生成")
    def generate_volume_chart(self, data: pd.DataFrame, title: str = "成交量分析",
                            save_path: Optional[str] = None) -> str:
        """
        生成成交量分析图

        Args:
            data: OHLCV数据
            title: 图表标题
            save_path: 保存路径（可选）

        Returns:
            Base64编码的图片字符串
        """
        try:
            with monitor_image_generation("成交量图"):
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8),
                                            gridspec_kw={'height_ratios': [3, 1]})
                fig.suptitle(title, fontsize=16)

                # 价格图
                ax1.plot(data.index, data['Close'], label='收盘价', linewidth=2, color='blue')
                ax1.set_title('价格走势')
                ax1.set_ylabel('价格')
                ax1.grid(True, alpha=0.3)
                ax1.legend()

                # 成交量图
                colors = ['red' if close >= open else 'green'
                         for close, open in zip(data['Close'], data['Open'])]
                ax2.bar(data.index, data['Volume'], color=colors, alpha=0.7)
                ax2.set_title('成交量')
                ax2.set_ylabel('成交量')
                ax2.grid(True, alpha=0.3)

                # 添加成交量移动平均线
                if len(data) >= 20:
                    vol_ma = data['Volume'].rolling(window=20).mean()
                    ax2.plot(data.index, vol_ma, label='成交量MA20', color='orange', linewidth=2)
                    ax2.legend()

                plt.tight_layout()

                # 转换为base64
                buffer = io.BytesIO()
                fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
                buffer.seek(0)
                image_base64 = base64.b64encode(buffer.getvalue()).decode()
                plt.close(fig)

                # 保存到文件（如果指定了路径）
                if save_path:
                    with open(save_path, 'wb') as f:
                        f.write(base64.b64decode(image_base64))

                return image_base64

        except Exception as e:
            raise ValueError(f"成交量图生成失败: {str(e)}")

    def generate_summary_chart(self, data: pd.DataFrame, indicators: dict,
                             decision: dict, title: str = "综合分析图表") -> str:
        """
        生成综合分析图表

        Args:
            data: OHLCV数据
            indicators: 技术指标数据
            decision: 决策数据
            title: 图表标题

        Returns:
            Base64编码的图片字符串
        """
        try:
            # 创建更大的画布来容纳更多信息
            fig = plt.figure(figsize=(16, 12))
            gs = fig.add_gridspec(4, 2, height_ratios=[2, 1, 1, 1], width_ratios=[3, 1])

            # 主图：K线图
            ax_main = fig.add_subplot(gs[0, 0])
            ax_main.plot(data.index, data['Close'], label='收盘价', linewidth=2)

            if len(data) >= 20:
                ma20 = data['Close'].rolling(window=20).mean()
                ax_main.plot(data.index, ma20, label='MA20', alpha=0.7)
            if len(data) >= 50:
                ma50 = data['Close'].rolling(window=50).mean()
                ax_main.plot(data.index, ma50, label='MA50', alpha=0.7)

            ax_main.set_title(f'{title} - 价格走势')
            ax_main.set_ylabel('价格')
            ax_main.legend()
            ax_main.grid(True, alpha=0.3)

            # 决策面板
            ax_decision = fig.add_subplot(gs[0, 1])
            ax_decision.axis('off')

            decision_text = f"""
            最终决策: {decision.get('action', 'UNKNOWN')}

            置信度: {decision.get('confidence', 0):.1%}

            理由: {decision.get('reasoning', '暂无')[:50]}...

            风险回报比: {decision.get('risk_reward', '暂无')}

            预测时间: {decision.get('time_horizon', '暂无')}
            """

            decision_color = 'green' if decision.get('action') == '做多' else 'red' if decision.get('action') == '做空' else 'gray'
            ax_decision.text(0.1, 0.5, decision_text, fontsize=12,
                           verticalalignment='center', bbox=dict(boxstyle='round',
                           facecolor=decision_color, alpha=0.1))

            # RSI图
            ax_rsi = fig.add_subplot(gs[1, 0])
            if "rsi" in indicators:
                rsi_values = indicators["rsi"]["rsi"]
                rsi_length = min(len(rsi_values), len(data))
                ax_rsi.plot(data.index[-rsi_length:], rsi_values[-rsi_length:], label='RSI', color='purple')
                ax_rsi.axhline(y=70, color='red', linestyle='--', alpha=0.7)
                ax_rsi.axhline(y=30, color='green', linestyle='--', alpha=0.7)
                ax_rsi.set_title('RSI指标')
                ax_rsi.set_ylabel('RSI')
                ax_rsi.set_ylim(0, 100)
                ax_rsi.grid(True, alpha=0.3)

            # 信号汇总图
            ax_signals = fig.add_subplot(gs[1, 1])
            ax_signals.axis('off')

            if "summary" in indicators:
                summary = indicators["summary"]
                signals_text = f"""
                技术信号汇总:

                总体信号: {summary.get('overall_signal', 'neutral').upper()}

                看涨信号 ({len(summary.get('bullish_signals', []))}):
                {chr(10).join(f'• {s}' for s in summary.get('bullish_signals', [])[:3])}

                看跌信号 ({len(summary.get('bearish_signals', []))}):
                {chr(10).join(f'• {s}' for s in summary.get('bearish_signals', [])[:3])}
                """
                ax_signals.text(0.1, 0.5, signals_text, fontsize=10,
                              verticalalignment='center', bbox=dict(boxstyle='round',
                              facecolor='lightblue', alpha=0.1))

            # MACD图
            ax_macd = fig.add_subplot(gs[2, :])
            if "macd" in indicators:
                macd_data = indicators["macd"]
                macd_length = min(len(macd_data["macd"]), len(data))

                x_axis = data.index[-macd_length:]
                ax_macd.plot(x_axis, macd_data["macd"][-macd_length:], label='MACD', linewidth=2)
                ax_macd.plot(x_axis, macd_data["signal"][-macd_length:], label='Signal', linewidth=2)

                histogram = macd_data["histogram"][-macd_length:]
                colors = ['red' if h < 0 else 'green' for h in histogram]
                ax_macd.bar(x_axis, histogram, color=colors, alpha=0.6, label='Histogram')

                ax_macd.set_title('MACD指标')
                ax_macd.set_ylabel('MACD')
                ax_macd.axhline(y=0, color='black', linestyle='-', alpha=0.3)
                ax_macd.legend()
                ax_macd.grid(True, alpha=0.3)

            # 成交量图
            ax_volume = fig.add_subplot(gs[3, :])
            colors = ['red' if close >= open else 'green'
                     for close, open in zip(data['Close'], data['Open'])]
            ax_volume.bar(data.index, data['Volume'], color=colors, alpha=0.7)
            ax_volume.set_title('成交量')
            ax_volume.set_ylabel('成交量')
            ax_volume.grid(True, alpha=0.3)

            plt.tight_layout()

            # 转换为base64
            buffer = io.BytesIO()
            fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close(fig)

            return image_base64

        except Exception as e:
            raise ValueError(f"综合图表生成失败: {str(e)}")


# 全局图表生成器实例
chart_generator = ChartGenerator()

# 向后兼容的函数
def generate_kline_image(data: pd.DataFrame, title: str = "K线图") -> str:
    """生成K线图（向后兼容）"""
    return chart_generator.generate_kline_chart(data, title)


def generate_trend_image(data: pd.DataFrame, indicators: dict, title: str = "技术指标分析图") -> str:
    """生成趋势图（向后兼容）"""
    return chart_generator.generate_trend_chart(data, indicators, title)