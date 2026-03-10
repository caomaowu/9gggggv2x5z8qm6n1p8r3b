from typing import Dict
import time
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

import sys
import io
# 在文件开头添加
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

# 添加根目录到路径以支持绝对导入
import sys
from pathlib import Path
# sys.path hack removed

from app.agents.agent_state import IndicatorAgentState
from app.agents.decision.decision_agent_original import create_final_trade_decider_original
from app.utils.graph_util import TechnicalTools
from app.agents.indicator_agent import create_indicator_agent
from app.agents.pattern_agent import create_pattern_agent
from app.agents.trend_agent import create_trend_agent


class SetGraph:
    def __init__(
        self,
        indicator_llm: ChatOpenAI,
        pattern_llm: ChatOpenAI,
        trend_llm: ChatOpenAI,
        decision_llm: ChatOpenAI,
        toolkit: TechnicalTools,
        tool_nodes: Dict[str, ToolNode],
        decision_agent_version: str = "original",
        include_decision_agent: bool = True,
    ):
        self.indicator_llm = indicator_llm
        self.pattern_llm = pattern_llm
        self.trend_llm = trend_llm
        self.decision_llm = decision_llm
        self.toolkit = toolkit
        self.tool_nodes = tool_nodes
        self.decision_agent_version = decision_agent_version
        self.include_decision_agent = include_decision_agent

    def set_graph(self):
        """
        设置图结构，实现三个分析智能体顺序启动（间隔4秒和7秒），
        决策智能体等待所有分析完成后立即执行
        """
        # Create analyst nodes
        agent_nodes = {}

        # create nodes for indicator agent - 哈雷酱修改：使用独立的 indicator_llm
        agent_nodes["indicator"] = create_indicator_agent(self.indicator_llm, self.toolkit)

        # create nodes for pattern agent
        agent_nodes["pattern"] = create_pattern_agent(
            self.pattern_llm, self.toolkit
        )

        # create nodes for trend agent
        agent_nodes["trend"] = create_trend_agent(
            self.trend_llm, self.toolkit
        )

        # create nodes for decision agent - 哈雷酱的AI版本功能！
        try:
            from app.agents.decision.decision_agent_factory import get_decision_agent_factory
            factory = get_decision_agent_factory()
            decision_agent_node = factory.create_agent(self.decision_agent_version, self.decision_llm)
            print(f"[AI版本] 图形设置使用决策智能体版本: {self.decision_agent_version}")
        except Exception as e:
            print(f"[AI版本] 使用决策智能体工厂失败，回退到原始版本: {e}")
            decision_agent_node = create_final_trade_decider_original(self.decision_llm)

        # create graph
        graph = StateGraph(IndicatorAgentState)

        # add rest of the nodes
        if self.include_decision_agent:
            graph.add_node("Decision Maker", decision_agent_node)

        # 创建并行启动协调器
        def sequential_start_coordinator(state):
            """
            协调三个分析智能体的顺序启动
            """
            print("🚀 开始顺序启动分析智能体...")

            # 创建共享状态和结果收集器
            shared_state = state.copy()
            results = {}
            completion_events = {}

            def run_agent_with_delay(agent_name, agent_node, delay):
                """
                延迟启动智能体并收集结果
                """
                if delay > 0:
                    print(f"⏳ {agent_name} 智能体将在 {delay} 秒后启动...")
                    time.sleep(delay)

                print(f"🔄 启动 {agent_name} 智能体...")
                try:
                    result = agent_node(shared_state)
                    results[agent_name] = result
                    completion_events[agent_name] = True
                    print(f"✅ {agent_name} 智能体完成")
                    return result
                except Exception as e:
                    print(f"❌ {agent_name} 智能体失败: {e}")
                    results[agent_name] = {"error": str(e)}
                    completion_events[agent_name] = True
                    return {"error": str(e)}

            # 启动三个分析智能体，间隔调整为4秒和7秒（更安全）
            with ThreadPoolExecutor(max_workers=3) as executor:
                # 提交任务，分别延迟 0, 5.0, 8.0 秒
                futures = [
                    executor.submit(run_agent_with_delay, "Indicator", agent_nodes["indicator"], 0),
                    executor.submit(run_agent_with_delay, "Pattern", agent_nodes["pattern"], 5.0),
                    executor.submit(run_agent_with_delay, "Trend", agent_nodes["trend"], 8.0)
                ]

                # 等待所有任务完成
                for future in futures:
                    future.result()

            if self.include_decision_agent:
                print("🎉 所有分析智能体完成，准备启动决策智能体...")

            # 整合所有分析结果到状态中
            combined_messages = []
            for agent_name, result in results.items():
                if "messages" in result and result["messages"]:
                    combined_messages.extend(result["messages"])

                # 保存各个智能体的报告
                if f"{agent_name.lower()}_report" in result:
                    shared_state[f"{agent_name.lower()}_report"] = result[f"{agent_name.lower()}_report"]

                # 保存计算数据和图像
                if "indicators_data" in result:
                    shared_state["indicators_data"] = result["indicators_data"]
                
                # 单周期图表
                if "pattern_image" in result:
                    shared_state["pattern_image"] = result["pattern_image"]
                if "trend_image" in result:
                    shared_state["trend_image"] = result["trend_image"]
                
                # 多周期图表 (哈雷酱修复：支持多周期数据传递)
                if "pattern_images" in result:
                    shared_state["pattern_images"] = result["pattern_images"]
                if "trend_images" in result:
                    shared_state["trend_images"] = result["trend_images"]
                if "multi_timeframe_mode" in result:
                    shared_state["multi_timeframe_mode"] = result["multi_timeframe_mode"]
                if "timeframes" in result:
                    shared_state["timeframes"] = result["timeframes"]

                # 哈雷酱添加：保存价格信息和指标数据（从技术指标智能体获取）
                if agent_name.lower() == "indicator":
                    if "latest_price" in result:
                        shared_state["latest_price"] = result["latest_price"]
                    if "price_info" in result:
                        shared_state["price_info"] = result["price_info"]
                    if "indicator_data" in result:
                        shared_state["indicator_data"] = result["indicator_data"]

            shared_state["messages"] = combined_messages
            shared_state["analysis_results"] = results

            return shared_state

        # 添加协调器节点
        graph.add_node("Sequential Coordinator", sequential_start_coordinator)

        # set start of graph
        graph.add_edge(START, "Sequential Coordinator")
        if self.include_decision_agent:
            graph.add_edge("Sequential Coordinator", "Decision Maker")
            graph.add_edge("Decision Maker", END)
        else:
            graph.add_edge("Sequential Coordinator", END)

        return graph.compile()
