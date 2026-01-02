"""
Technical Indicators - 技术指标计算工具
从graph_util.py中分离出来的纯技术指标计算功能
作者：哈雷酱（傲娇大小姐工程师）
"""

import numpy as np
import pandas as pd
import talib
from typing import Annotated

from .performance import performance_monitor, monitor_computation
# from ..core.config import config  # 暂时注释，避免相对导入问题


class TechnicalTools:
    """
    技术指标计算工具集

    哼哼！本小姐把原来469行的混合文件拆分了，
    现在这个模块专门负责技术指标计算，职责单一！
    """

    def __init__(self):
        """初始化技术工具"""
        pass

    @performance_monitor("MACD计算")
    def calculate_macd(self, data: pd.DataFrame, fastperiod: int = 12,
                      slowperiod: int = 26, signalperiod: int = 9) -> dict:
        """计算MACD指标"""
        try:
            with monitor_computation("MACD技术指标"):
                macd, signal, histogram = talib.MACD(
                    data['Close'], fastperiod=fastperiod,
                    slowperiod=slowperiod, signalperiod=signalperiod
                )

                return {
                    "macd": macd.dropna().tolist(),
                    "signal": signal.dropna().tolist(),
                    "histogram": histogram.dropna().tolist(),
                    "latest": {
                        "macd": float(macd.iloc[-1]) if not pd.isna(macd.iloc[-1]) else 0,
                        "signal": float(signal.iloc[-1]) if not pd.isna(signal.iloc[-1]) else 0,
                        "histogram": float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else 0
                    }
                }
        except Exception as e:
            raise ValueError(f"MACD计算失败: {str(e)}")

    @performance_monitor("RSI计算")
    def calculate_rsi(self, data: pd.DataFrame, timeperiod: int = 14) -> dict:
        """计算RSI指标"""
        try:
            with monitor_computation("RSI技术指标"):
                rsi = talib.RSI(data['Close'], timeperiod=timeperiod)

                return {
                    "rsi": rsi.dropna().tolist(),
                    "latest": float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50,
                    "overbought": float(rsi.iloc[-1]) > 70 if not pd.isna(rsi.iloc[-1]) else False,
                    "oversold": float(rsi.iloc[-1]) < 30 if not pd.isna(rsi.iloc[-1]) else False
                }
        except Exception as e:
            raise ValueError(f"RSI计算失败: {str(e)}")

    @performance_monitor("ROC计算")
    def calculate_roc(self, data: pd.DataFrame, timeperiod: int = 10) -> dict:
        """计算ROC指标（变化率）"""
        try:
            with monitor_computation("ROC技术指标"):
                roc = talib.ROC(data['Close'], timeperiod=timeperiod)

                return {
                    "roc": roc.dropna().tolist(),
                    "latest": float(roc.iloc[-1]) if not pd.isna(roc.iloc[-1]) else 0,
                    "trend": "bullish" if float(roc.iloc[-1]) > 0 else "bearish" if not pd.isna(roc.iloc[-1]) else "neutral"
                }
        except Exception as e:
            raise ValueError(f"ROC计算失败: {str(e)}")

    @performance_monitor("随机指标计算")
    def calculate_stochastic(self, data: pd.DataFrame, fastk_period: int = 5,
                           slowk_period: int = 3, slowd_period: int = 3) -> dict:
        """计算随机指标（Stochastic Oscillator）"""
        try:
            with monitor_computation("随机指标"):
                slowk, slowd = talib.STOCH(
                    data['High'], data['Low'], data['Close'],
                    fastk_period=fastk_period,
                    slowk_period=slowk_period,
                    slowd_period=slowd_period
                )

                return {
                    "slowk": slowk.dropna().tolist(),
                    "slowd": slowd.dropna().tolist(),
                    "latest": {
                        "slowk": float(slowk.iloc[-1]) if not pd.isna(slowk.iloc[-1]) else 50,
                        "slowd": float(slowd.iloc[-1]) if not pd.isna(slowd.iloc[-1]) else 50
                    },
                    "overbought": float(slowk.iloc[-1]) > 80 if not pd.isna(slowk.iloc[-1]) else False,
                    "oversold": float(slowk.iloc[-1]) < 20 if not pd.isna(slowk.iloc[-1]) else False
                }
        except Exception as e:
            raise ValueError(f"随机指标计算失败: {str(e)}")

    @performance_monitor("威廉指标计算")
    def calculate_williams_r(self, data: pd.DataFrame, timeperiod: int = 14) -> dict:
        """计算威廉%R指标"""
        try:
            with monitor_computation("威廉%R指标"):
                williams_r = talib.WILLR(data['High'], data['Low'], data['Close'], timeperiod=timeperiod)

                return {
                    "williams_r": williams_r.dropna().tolist(),
                    "latest": float(williams_r.iloc[-1]) if not pd.isna(williams_r.iloc[-1]) else -50,
                    "overbought": float(williams_r.iloc[-1]) > -20 if not pd.isna(williams_r.iloc[-1]) else False,
                    "oversold": float(williams_r.iloc[-1]) < -80 if not pd.isna(williams_r.iloc[-1]) else False
                }
        except Exception as e:
            raise ValueError(f"威廉%R指标计算失败: {str(e)}")

    @performance_monitor("布林带计算")
    def calculate_bollinger_bands(self, data: pd.DataFrame, timeperiod: int = 20,
                                 nbdevup: int = 2, nbdevdn: int = 2) -> dict:
        """计算布林带"""
        try:
            with monitor_computation("布林带指标"):
                upperband, middleband, lowerband = talib.BBANDS(
                    data['Close'], timeperiod=timeperiod,
                    nbdevup=nbdevup, nbdevdn=nbdevdn
                )

                current_price = float(data['Close'].iloc[-1])

                return {
                    "upperband": upperband.dropna().tolist(),
                    "middleband": middleband.dropna().tolist(),
                    "lowerband": lowerband.dropna().tolist(),
                    "latest": {
                        "upper": float(upperband.iloc[-1]) if not pd.isna(upperband.iloc[-1]) else current_price * 1.02,
                        "middle": float(middleband.iloc[-1]) if not pd.isna(middleband.iloc[-1]) else current_price,
                        "lower": float(lowerband.iloc[-1]) if not pd.isna(lowerband.iloc[-1]) else current_price * 0.98
                    },
                    "position": "above_upper" if current_price > float(upperband.iloc[-1]) else
                               "below_lower" if current_price < float(lowerband.iloc[-1]) else
                               "within_bands" if not (pd.isna(upperband.iloc[-1]) or pd.isna(lowerband.iloc[-1])) else "unknown"
                }
        except Exception as e:
            raise ValueError(f"布林带计算失败: {str(e)}")

    def calculate_all_indicators(self, data: pd.DataFrame) -> dict:
        """计算所有技术指标"""
        if len(data) < 30:
            raise ValueError("数据不足，需要至少30根K线来计算技术指标")

        results = {}

        try:
            results["macd"] = self.calculate_macd(data)
            results["rsi"] = self.calculate_rsi(data)
            results["roc"] = self.calculate_roc(data)
            results["stochastic"] = self.calculate_stochastic(data)
            results["williams_r"] = self.calculate_williams_r(data)
            results["bollinger_bands"] = self.calculate_bollinger_bands(data)

            # 添加指标汇总
            results["summary"] = self._generate_indicator_summary(results)

        except Exception as e:
            raise ValueError(f"技术指标计算失败: {str(e)}")

        return results

    def _generate_indicator_summary(self, indicators: dict) -> dict:
        """生成技术指标汇总分析"""
        summary = {
            "overall_signal": "neutral",
            "bullish_signals": [],
            "bearish_signals": [],
            "neutral_signals": []
        }

        # MACD分析
        if "macd" in indicators:
            macd_data = indicators["macd"]["latest"]
            if macd_data["macd"] > macd_data["signal"] and macd_data["histogram"] > 0:
                summary["bullish_signals"].append("MACD金叉")
            elif macd_data["macd"] < macd_data["signal"] and macd_data["histogram"] < 0:
                summary["bearish_signals"].append("MACD死叉")

        # RSI分析
        if "rsi" in indicators:
            rsi_data = indicators["rsi"]
            if rsi_data["oversold"]:
                summary["bullish_signals"].append("RSI超卖反弹")
            elif rsi_data["overbought"]:
                summary["bearish_signals"].append("RSI超买回调")

        # 随机指标分析
        if "stochastic" in indicators:
            stoch_data = indicators["stochastic"]
            if stoch_data["oversold"]:
                summary["bullish_signals"].append("随机指标超卖")
            elif stoch_data["overbought"]:
                summary["bearish_signals"].append("随机指标超买")

        # 威廉指标分析
        if "williams_r" in indicators:
            williams_data = indicators["williams_r"]
            if williams_data["oversold"]:
                summary["bullish_signals"].append("威廉%R超卖")
            elif williams_data["overbought"]:
                summary["bearish_signals"].append("威廉%R超买")

        # ROC分析
        if "roc" in indicators:
            roc_data = indicators["roc"]
            if roc_data["trend"] == "bullish":
                summary["bullish_signals"].append("ROC上涨趋势")
            elif roc_data["trend"] == "bearish":
                summary["bearish_signals"].append("ROC下跌趋势")

        # 布林带分析
        if "bollinger_bands" in indicators:
            bb_data = indicators["bollinger_bands"]
            if bb_data["position"] == "above_upper":
                summary["bearish_signals"].append("价格突破布林带上轨")
            elif bb_data["position"] == "below_lower":
                summary["bullish_signals"].append("价格跌破布林带下轨")
            else:
                summary["neutral_signals"].append("价格在布林带内运行")

        # 综合信号判断
        bullish_count = len(summary["bullish_signals"])
        bearish_count = len(summary["bearish_signals"])

        if bullish_count > bearish_count + 1:
            summary["overall_signal"] = "bullish"
        elif bearish_count > bullish_count + 1:
            summary["overall_signal"] = "bearish"
        else:
            summary["overall_signal"] = "neutral"

        return summary


