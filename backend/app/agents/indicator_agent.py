"""
Agent for technical indicator analysis in high-frequency trading (HFT) context.
现在直接系统调用计算技术指标，然后让LLM分析结果，避免昂贵的LLM工具调用。
支持多时间框架分析。
"""

import copy
import json
import pandas as pd

from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# 哈雷酱的进度跟踪导入！
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from app.core.progress import update_agent_progress
except ImportError:
    # 如果导入失败，使用空函数避免破坏
    def update_agent_progress(agent_name, progress_within_agent=0, status=""):
        pass

# 哈雷酱的性能监控系统！
try:
    from app.utils.performance import performance_monitor, monitor_llm_call
except ImportError:
    # 如果导入失败，使用空装饰器
    def performance_monitor(stage_name=None):
        def decorator(func):
            return func
        return decorator
    def monitor_llm_call(model_name=None):
        return performance_monitor(f"LLM调用: {model_name}" if model_name else "LLM调用")


# 辅助函数：将 DataFrame 或其他格式转换为 list[dict]
def convert_to_list_of_dicts(data):
    """
    将各种格式的数据转换为 list[dict] 格式供工具调用
    """
    if isinstance(data, pd.DataFrame):
        # DataFrame -> list of dicts
        df_reset = data.reset_index()
        if 'Date' in df_reset.columns:
            df_reset['Date'] = df_reset['Date'].dt.strftime('%Y-%m-%d %H:%M:%S')
            df_reset.rename(columns={'Date': 'Datetime'}, inplace=True)
        return df_reset.to_dict(orient='records')
    elif isinstance(data, list):
        # 已经是 list 格式
        return data
    elif isinstance(data, dict):
        # dict 格式，尝试转换
        return data
    else:
        return data


def extract_latest_price(data):
    """
    提取最新价格，兼容多种数据格式
    """
    if isinstance(data, pd.DataFrame):
        return float(data['Close'].iloc[-1])
    elif isinstance(data, list) and len(data) > 0:
        return data[-1].get("Close")
    elif isinstance(data, dict) and "Close" in data and len(data["Close"]) > 0:
        return data["Close"][-1]
    return None


@performance_monitor("技术指标智能体")
def create_indicator_agent(llm, toolkit):
    """
    Create an indicator analysis agent node for HFT.
    现在直接系统调用计算技术指标，然后让LLM分析结果，避免昂贵的LLM工具调用。
    """

    @performance_monitor("技术指标智能体执行")
    def indicator_agent_node(state):
        # 哈雷酱的进度跟踪！
        update_agent_progress("indicator", 10, "正在启动技术指标分析智能体...")

        kline_data = state["kline_data"]
        time_frame = state["time_frame"]

        # 检测是否为多时间框架模式
        is_multi_tf = isinstance(kline_data, dict) and not any(
            key in ['Open', 'High', 'Low', 'Close', 'Volume', 'Datetime'] 
            for key in kline_data.keys()
        )
        
        if is_multi_tf:
            print(f"⚡ 多时间框架模式：检测到 {len(kline_data)} 个时间框架 - {list(kline_data.keys())}")
        else:
            print(f"🔹 单一时间框架模式：{time_frame}")

        # --- 直接系统调用计算所有技术指标 ---
        update_agent_progress("indicator", 30, "正在计算技术指标数据...")

        try:
            if is_multi_tf:
                # 多时间框架模式：循环计算每个时间框架
                multi_tf_indicators = {}
                
                for tf_name, tf_data in kline_data.items():
                    print(f"📊 正在计算 {tf_name} 时间框架的指标...")
                    indicator_results = {}
                    
                    # 转换为工具所需的格式
                    tf_data_list = convert_to_list_of_dicts(tf_data)
                    
                    # 计算MACD
                    try:
                        macd_result = toolkit.compute_macd.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["MACD"] = macd_result
                    except Exception as e:
                        print(f"MACD计算失败 ({tf_name}): {e}")
                        indicator_results["MACD"] = {"error": str(e)}

                    # 计算RSI
                    try:
                        rsi_result = toolkit.compute_rsi.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["RSI"] = rsi_result
                    except Exception as e:
                        print(f"RSI计算失败 ({tf_name}): {e}")
                        indicator_results["RSI"] = {"error": str(e)}

                    # 计算ROC
                    try:
                        roc_result = toolkit.compute_roc.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["ROC"] = roc_result
                    except Exception as e:
                        print(f"ROC计算失败 ({tf_name}): {e}")
                        indicator_results["ROC"] = {"error": str(e)}

                    # 计算Stochastic
                    try:
                        stoch_result = toolkit.compute_stoch.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["Stochastic"] = stoch_result
                    except Exception as e:
                        print(f"Stochastic计算失败 ({tf_name}): {e}")
                        indicator_results["Stochastic"] = {"error": str(e)}

                    # 计算Williams %R
                    try:
                        willr_result = toolkit.compute_willr.invoke({"kline_data": copy.deepcopy(tf_data_list)})
                        indicator_results["Williams_R"] = willr_result
                    except Exception as e:
                        print(f"Williams %R计算失败 ({tf_name}): {e}")
                        indicator_results["Williams_R"] = {"error": str(e)}
                    
                    multi_tf_indicators[tf_name] = indicator_results
                    
            else:
                # 单一时间框架模式：保持原有逻辑
                # 直接调用工具计算技术指标，避免LLM工具调用
                indicator_results = {}

                # 计算MACD
                try:
                    macd_result = toolkit.compute_macd.invoke({"kline_data": copy.deepcopy(kline_data)})
                    indicator_results["MACD"] = macd_result
                except Exception as e:
                    print(f"MACD计算失败: {e}")
                    indicator_results["MACD"] = {"error": str(e)}

                # 计算RSI
                try:
                    rsi_result = toolkit.compute_rsi.invoke({"kline_data": copy.deepcopy(kline_data)})
                    indicator_results["RSI"] = rsi_result
                except Exception as e:
                    print(f"RSI计算失败: {e}")
                    indicator_results["RSI"] = {"error": str(e)}

                # 计算ROC
                try:
                    roc_result = toolkit.compute_roc.invoke({"kline_data": copy.deepcopy(kline_data)})
                    indicator_results["ROC"] = roc_result
                except Exception as e:
                    print(f"ROC计算失败: {e}")
                    indicator_results["ROC"] = {"error": str(e)}

                # 计算Stochastic
                try:
                    stoch_result = toolkit.compute_stoch.invoke({"kline_data": copy.deepcopy(kline_data)})
                    indicator_results["Stochastic"] = stoch_result
                except Exception as e:
                    print(f"Stochastic计算失败: {e}")
                    indicator_results["Stochastic"] = {"error": str(e)}

                # 计算Williams %R
                try:
                    willr_result = toolkit.compute_willr.invoke({"kline_data": copy.deepcopy(kline_data)})
                    indicator_results["Williams_R"] = willr_result
                except Exception as e:
                    print(f"Williams %R计算失败: {e}")
                    indicator_results["Williams_R"] = {"error": str(e)}

            update_agent_progress("indicator", 60, "正在生成技术指标分析报告...")

        except Exception as e:
            update_agent_progress("indicator", 100, "技术指标计算失败")
            return {
                "messages": state.get("messages", []),
                "indicator_report": f"技术指标计算失败: {str(e)}",
                "error": str(e)
            }

        # --- 提取最新价格信息 ---
        latest_price = None
        if is_multi_tf:
            # 多时间框架：使用第一个时间框架的最新价格
            first_tf = list(kline_data.keys())[0]
            first_tf_data = kline_data[first_tf]
            latest_price = extract_latest_price(first_tf_data)
        else:
            # 单一时间框架：原有逻辑
            # 兼容 list of dicts (Record-oriented) 和 dict of lists (Column-oriented) 格式
            if isinstance(kline_data, list) and len(kline_data) > 0:
                # Record-oriented: [{'Close': 100}, ...]
                latest_price = kline_data[-1].get("Close")
            elif isinstance(kline_data, dict) and "Close" in kline_data and len(kline_data["Close"]) > 0:
                # Column-oriented: {'Close': [100, ...]}
                latest_price = kline_data["Close"][-1]

        # --- 将计算结果整理为结构化文本供LLM分析 ---
        price_info = f"Current closing price: {latest_price}\n\n" if latest_price else ""
        
        if is_multi_tf:
            # Multi-timeframe mode: English prompt
            indicators_text = f"""
⚡ **Technical Analysis - Multi-Timeframe**
Trading Pair: {state.get('stock_name', 'Unknown')} | Timeframe: {time_frame}

💰 **Current Price**: {latest_price if latest_price else 'Unknown'}
{price_info}

🌐 **Multi-Timeframe Analysis**: Analyzing {len(multi_tf_indicators)} timeframes

---

"""
            
            # Generate indicator display for each timeframe
            for tf_name, indicators in multi_tf_indicators.items():
                macd_json = json.dumps(indicators.get("MACD", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
                rsi_json = json.dumps(indicators.get("RSI", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
                roc_json = json.dumps(indicators.get("ROC", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
                stoch_json = json.dumps(indicators.get("Stochastic", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
                willr_json = json.dumps(indicators.get("Williams_R", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
                
                indicators_text += f"""
## 📊 **{tf_name} Timeframe Analysis**

### 🔥 MACD Indicator
{macd_json}

### ⚡ RSI Indicator
{rsi_json}

### 📈 ROC Indicator
{roc_json}

### 🌊 Stochastic Indicator
{stoch_json}

### 🎯 Williams %R Indicator
{willr_json}

---

"""
            
            # Append analysis instructions for multi-timeframe
            indicators_text += """
## 📊 Analysis Task

You have access to the above technical indicators across multiple timeframes.
**Autonomously select and analyze** the timeframes and indicators that are most relevant.
Look for confluence or divergence between timeframes.
Focus on the signals that provide the clearest insight into market direction and momentum.
Provide a technical analysis.
"""
        else:
            # Single timeframe mode: Original English prompt
            # Escape JSON curly braces to avoid LangChain template variable parsing issues
            macd_json = json.dumps(indicator_results.get("MACD", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
            rsi_json = json.dumps(indicator_results.get("RSI", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
            roc_json = json.dumps(indicator_results.get("ROC", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
            stoch_json = json.dumps(indicator_results.get("Stochastic", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
            willr_json = json.dumps(indicator_results.get("Williams_R", {}), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")

            # Escape complete OHLC data
            ohlc_data_json = json.dumps(kline_data, indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")

            # Original HFT-style English prompt
            indicators_text = f"""
You are a high-frequency trading (HFT) analyst assistant operating under time-sensitive conditions.
You must analyze technical indicators to support fast-paced trading execution.

⚠️ The OHLC data provided is from {time_frame} intervals, reflecting recent market behavior.
You must interpret this data quickly and accurately.

Here is the OHLC data:
{ohlc_data_json}

---

### 🔥 MACD Indicator
{macd_json}

### ⚡ RSI Indicator
{rsi_json}

### 📈 ROC Indicator
{roc_json}

### 🌊 Stochastic Indicator
{stoch_json}

### 🎯 Williams %R Indicator
{willr_json}

---

## 📊 Analysis Task

You have access to the above technical indicators. 
**Autonomously select and analyze** the indicators that are most relevant to the current market structure. 
Focus on the signals that provide the clearest insight into market direction and momentum.
Provide a technical analysis.
"""

        # --- LLM分析预计算的指标结果 ---
        system_prompt_text = """You are a high-frequency trading (HFT) analyst assistant operating under time-sensitive conditions.
You must analyze technical indicators to support fast-paced trading execution.

I have pre-computed several technical indicators for you.
Your task is to review this data and **autonomously determine** which indicators provide the strongest signals for the current market context.
Avoid mechanical listing of all data. Focus on the critical signals that matter for trading decisions."""

        
        analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt_text),
            ("human", indicators_text)
        ])

        try:
            chain = analysis_prompt | llm
            final_response = chain.invoke({})
            indicator_report_content = final_response.content
        except Exception as e:
            print(f"❌ 技术指标 LLM 分析失败: {e}")
            indicator_report_content = f"Technical indicator analysis failed (LLM Error): {str(e)}"
            # 即使 LLM 失败，我们也返回计算出的指标数据
            
        update_agent_progress("indicator", 100, "技术指标分析完成")
        return {
            "messages": state.get("messages", []) + ([final_response] if 'final_response' in locals() else []),
            "indicator_report": indicator_report_content,
            "indicator_data": multi_tf_indicators if is_multi_tf else indicator_results,
            "latest_price": latest_price,
            "price_info": price_info,
            "multi_timeframe_mode": is_multi_tf,
            "timeframes": list(kline_data.keys()) if is_multi_tf else [time_frame]
        }

    return indicator_agent_node