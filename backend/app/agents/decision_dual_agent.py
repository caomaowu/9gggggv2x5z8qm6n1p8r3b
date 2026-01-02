"""
双模型决策智能体
哈雷酱的AI模型对战系统！(￣▽￣)／

这个模块实现了双模型并行决策功能，
支持两个不同的AI模型同时进行分析，并提供对比结果。
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# 哈雷酱的模块化导入！
import sys
from pathlib import Path
# sys.path hack removed

from app.agents.decision_agent_factory import get_decision_agent_factory
from app.agents.decision_configs import risk_control
from app.core.dual_model_config import get_dual_model_config_manager
from app.utils.performance import performance_monitor


@dataclass
class ModelResult:
    """模型分析结果"""
    model_id: str
    model_name: str
    decision: str
    confidence: float
    reasoning: str
    risk_reward: str
    time_horizon: str
    execution_time: float
    error: Optional[str] = None
    timestamp: str = None
    # 哈雷酱：添加止盈止损和市场环境字段
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    stop_loss_adj: Optional[float] = None
    take_profit_adj: Optional[float] = None
    market_environment: Optional[str] = None
    volatility_assessment: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


@dataclass
class DualModelAnalysisResult:
    """双模型分析结果"""
    model_1_result: ModelResult
    model_2_result: Optional[ModelResult]
    comparison: Dict[str, Any]
    total_execution_time: float

    @property
    def is_dual_mode(self) -> bool:
        """是否为双模型模式"""
        return self.model_2_result is not None

    @property
    def has_consensus(self) -> bool:
        """两个模型是否达成一致"""
        if not self.is_dual_mode:
            return True
        return self.model_1_result.decision == self.model_2_result.decision

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，支持JSON序列化 - 哈雷酱的修复！"""
        result = {
            "model_1_result": {
                "model_id": self.model_1_result.model_id,
                "model_name": self.model_1_result.model_name,
                "decision": self.model_1_result.decision,
                "confidence": self.model_1_result.confidence,
                "reasoning": self.model_1_result.reasoning,
                "risk_reward": self.model_1_result.risk_reward,
                "time_horizon": self.model_1_result.time_horizon,
                "execution_time": self.model_1_result.execution_time,
                "error": self.model_1_result.error,
                "timestamp": self.model_1_result.timestamp,
                # 哈雷酱：添加止盈止损和市场环境字段！
                "stop_loss": self.model_1_result.stop_loss,
                "take_profit": self.model_1_result.take_profit,
                "stop_loss_adj": self.model_1_result.stop_loss_adj,
                "take_profit_adj": self.model_1_result.take_profit_adj,
                "market_environment": self.model_1_result.market_environment,
                "volatility_assessment": self.model_1_result.volatility_assessment
            },
            "comparison": self.comparison,
            "total_execution_time": self.total_execution_time,
            "is_dual_mode": self.is_dual_mode,
            "has_consensus": self.has_consensus
        }

        # 添加模型2结果（如果存在）
        if self.model_2_result:
            result["model_2_result"] = {
                "model_id": self.model_2_result.model_id,
                "model_name": self.model_2_result.model_name,
                "decision": self.model_2_result.decision,
                "confidence": self.model_2_result.confidence,
                "reasoning": self.model_2_result.reasoning,
                "risk_reward": self.model_2_result.risk_reward,
                "time_horizon": self.model_2_result.time_horizon,
                "execution_time": self.model_2_result.execution_time,
                "error": self.model_2_result.error,
                "timestamp": self.model_2_result.timestamp,
                # 哈雷酱：添加止盈止损和市场环境字段！
                "stop_loss": self.model_2_result.stop_loss,
                "take_profit": self.model_2_result.take_profit,
                "stop_loss_adj": self.model_2_result.stop_loss_adj,
                "take_profit_adj": self.model_2_result.take_profit_adj,
                "market_environment": self.model_2_result.market_environment,
                "volatility_assessment": self.model_2_result.volatility_assessment
            }

        return result


class DualModelDecisionAgent:
    """双模型决策智能体"""

    def __init__(self):
        """初始化双模型决策智能体"""
        self.factory = get_decision_agent_factory()
        self.config_manager = get_dual_model_config_manager()
        self.executor = ThreadPoolExecutor(max_workers=2)

    def analyze_with_dual_models(self, state: Dict[str, Any]) -> DualModelAnalysisResult:
        """
        使用双模型进行分析

        Args:
            state: 分析状态数据

        Returns:
            DualModelAnalysisResult: 双模型分析结果
        """
        start_time = time.time()

        # 哈雷酱增强：输出启动信息！
        stock_name = state.get("stock_name", state.get("display_name", "未知"))
        timeframe = state.get("timeframe", "未知")
        print(f"🚀 [双模型决策系统] 开始分析: {stock_name} ({timeframe})")

        # 获取配置
        dual_config = self.config_manager.get_dual_model_config()
        is_enabled = dual_config.get("enabled", False)

        print(f"⚙️  [双模型配置] 双模型模式: {'启用' if is_enabled else '禁用'}")

        if not is_enabled:
            # 单模型模式
            print("📊 [双模型决策系统] 执行单模型分析...")
            return self._analyze_single_model(state, start_time)
        else:
            # 双模型模式
            model_1 = dual_config.get("model_1", "未知")
            model_2 = dual_config.get("model_2", "未知")
            print(f"🔄 [双模型决策系统] 执行双模型对比分析:")
            print(f"   模型A: {model_1}")
            print(f"   模型B: {model_2}")
            return self._analyze_dual_models(state, dual_config, start_time)

    def _analyze_single_model(self, state: Dict[str, Any], start_time: float) -> DualModelAnalysisResult:
        """单模型分析"""
        try:
            # 哈雷酱：直接创建LLM对象，避免配置问题！
            from app.core.config import config
            from langchain_openai import ChatOpenAI

            # 创建LLM对象
            llm = ChatOpenAI(
                model=config.llm.agent_model,
                temperature=config.llm.agent_temperature,
                api_key=config.llm.api_key,
                base_url=config.llm.base_url
            )

            print(f"[单模型分析] 创建LLM: {config.llm.agent_model}")

            # 创建智能体（尊重状态中的版本选择，默认constrained）
            version = state.get("decision_agent_version", "constrained")
            agent = self.factory.create_agent(version, llm)

            # 执行分析
            result = agent(state)

            # 解析结果
            model_result = self._parse_model_result(result, config.llm.agent_model, "主模型", state)

            # 创建对比结果
            comparison = {
                "mode": "single",
                "model_count": 1,
                "consensus": True,
                "message": "单模型分析模式"
            }

            execution_time = time.time() - start_time

            return DualModelAnalysisResult(
                model_1_result=model_result,
                model_2_result=None,
                comparison=comparison,
                total_execution_time=execution_time
            )

        except Exception as e:
            print(f"[单模型分析] 分析失败: {e}")

            # 错误处理
            model_result = ModelResult(
                model_id="主模型",
                model_name="主模型",
                decision="错误",
                confidence=0.0,
                reasoning=f"分析失败: {str(e)}",
                risk_reward="N/A",
                time_horizon="N/A",
                execution_time=time.time() - start_time,
                error=str(e)
            )

            comparison = {
                "mode": "single",
                "model_count": 1,
                "consensus": False,
                "message": "分析过程中出现错误"
            }

            return DualModelAnalysisResult(
                model_1_result=model_result,
                model_2_result=None,
                comparison=comparison,
                total_execution_time=time.time() - start_time
            )

    def _analyze_dual_models(self, state: Dict[str, Any], dual_config: Dict[str, Any], start_time: float) -> DualModelAnalysisResult:
        """双模型并行分析"""
        model_1_config = {
            "model": dual_config.get("model_1", ""),
            "temperature": dual_config.get("temperature_1", 0.1)
        }
        model_2_config = {
            "model": dual_config.get("model_2", ""),
            "temperature": dual_config.get("temperature_2", 0.1)
        }

        # 并行执行两个模型的分析
        future_1 = self.executor.submit(self._analyze_single_model_async, state, model_1_config, "模型A")

        # 2秒延迟启动第二个模型，避免API限速
        time.sleep(2)
        future_2 = self.executor.submit(self._analyze_single_model_async, state, model_2_config, "模型B")

        # 等待结果
        model_1_result = future_1.result()
        model_2_result = future_2.result()

        # 生成对比分析
        comparison = self._generate_comparison(model_1_result, model_2_result)

        total_execution_time = time.time() - start_time

        return DualModelAnalysisResult(
            model_1_result=model_1_result,
            model_2_result=model_2_result,
            comparison=comparison,
            total_execution_time=total_execution_time
        )

    def _analyze_single_model_async(self, state: Dict[str, Any], model_config: Dict[str, Any], model_name: str) -> ModelResult:
        """异步执行单个模型分析"""
        start_time = time.time()

        try:
            # 哈雷酱增强：状态数据完整性验证！
            self._validate_state_data(state, model_name)

            # 哈雷酱：直接创建新的LLM对象和智能体，避免配置问题！
            from app.core.config import config
            from langchain_openai import ChatOpenAI

            # 创建新的LLM对象
            llm = ChatOpenAI(
                model=model_config.get("model", config.llm.agent_model),
                temperature=model_config.get("temperature", 0.1),
                api_key=config.llm.api_key,
                base_url=config.llm.base_url
            )

            print(f"[双模型分析] 创建LLM: {model_config.get('model')}")

            # 使用工厂按版本创建智能体（来自状态）
            version = state.get("decision_agent_version", "constrained")
            agent = self.factory.create_agent(version, llm)

            # 执行分析
            print(f"[{model_name}] 🧠 开始执行AI决策分析...")
            result = agent(state)
            print(f"[{model_name}] ✅ AI分析完成，开始解析结果...")

            # 哈雷酱修复：从决策智能体结果中提取final_trade_decision
            if "final_trade_decision" in result:
                decision_json = result["final_trade_decision"]
                print(f"[{model_name}] 📋 提取到决策JSON: {decision_json[:100]}...")
                model_result = self._parse_model_result(decision_json, model_config["model"], model_name, state)
            else:
                print(f"[{model_name}] ⚠️  未找到final_trade_decision字段，使用完整结果")
                model_result = self._parse_model_result(result, model_config["model"], model_name, state)

            model_result.execution_time = time.time() - start_time

            # 哈雷酱增强：输出关键结果信息！
            print(f"[{model_name}] 🎯 决策结果: {model_result.decision}")
            print(f"[{model_name}] 📊 置信度: {model_result.confidence:.2f}")
            print(f"[{model_name}] ⏱️  执行时间: {model_result.execution_time:.2f}秒")

            return model_result

        except Exception as e:
            print(f"[双模型分析] {model_name} 分析失败: {e}")

            return ModelResult(
                model_id=model_config.get("model", "Unknown"),
                model_name=model_name,
                decision="错误",
                confidence=0.0,
                reasoning=f"分析失败: {str(e)}",
                risk_reward="N/A",
                time_horizon="N/A",
                execution_time=time.time() - start_time,
                error=str(e)
            )

    def _parse_model_result(self, result: Dict[str, Any], model_id: str, model_name: str, state: Dict[str, Any]) -> ModelResult:
        """解析模型结果"""
        if "error" in result:
            return ModelResult(
                model_id=model_id,
                model_name=model_name,
                decision="错误",
                confidence=0.0,
                reasoning=result["error"],
                risk_reward="N/A",
                time_horizon="N/A",
                error=result["error"]
            )

        # 哈雷酱修复：解析JSON字符串格式和字典格式！
        if isinstance(result, str):
            # 如果是JSON字符串，先解析
            try:
                import json
                result = json.loads(result)
                print(f"[{model_name}] 📄 JSON解析成功，字段数: {len(result)}")
            except Exception as e:
                print(f"[{model_name}] ⚠️  JSON解析失败: {e}")
                print(f"[{model_name}] 原始数据: {result[:200]}...")
                return ModelResult(
                    model_id=model_id,
                    model_name=model_name,
                    decision="解析错误",
                    confidence=0.0,
                    reasoning=f"JSON解析失败: {str(e)}",
                    risk_reward="N/A",
                    time_horizon="N/A",
                    error="JSON解析失败"
                )

        # 提取决策信息 - 支持多种字段名
        decision = result.get("decision", result.get("final_trade_decision", "未知"))

        # 置信度：支持多种格式
        confidence_str = result.get("confidence_level", result.get("confidence", "0"))
        try:
            if isinstance(confidence_str, str) and '%' in confidence_str:
                confidence = float(confidence_str.replace('%', '')) / 100
            elif confidence_str in ["低", "中", "高"]:
                confidence_map = {"低": 0.3, "中": 0.6, "高": 0.8}
                confidence = confidence_map.get(confidence_str, 0.0)
            else:
                confidence = float(confidence_str)
        except Exception as e:
            print(f"[{model_name}] ⚠️  置信度解析失败: {e}, 原值: {confidence_str}")
            confidence = 0.0

        reasoning = result.get("justification", result.get("reasoning", "无推理说明"))

        risk_reward_ratio = result.get("risk_reward_ratio", result.get("risk_reward", "N/A"))
        risk_reward = "N/A"

        time_horizon = result.get("forecast_horizon", result.get("time_horizon", "N/A"))

        # 哈雷酱修复：提取止盈止损价格！
        stop_loss = result.get("stop_loss", None)
        take_profit = result.get("take_profit", None)
        market_environment = result.get("market_environment", "未知")
        volatility_assessment = result.get("volatility_assessment", "未知")

        print(f"[{model_name}] ✅ 解析完成:")
        print(f"[{model_name}]    - 决策: {decision}")
        print(f"[{model_name}]    - 置信度: {confidence:.2f} (原始: {confidence_str})")
        print(f"[{model_name}]    - 风险回报比: {risk_reward}")
        print(f"[{model_name}]    - 时间框架: {time_horizon}")
        print(f"[{model_name}]    - 市场环境: {market_environment}")
        print(f"[{model_name}]    - 波动性: {volatility_assessment}")
        print(f"[{model_name}]    - 止损价格: {stop_loss}")
        print(f"[{model_name}]    - 止盈价格: {take_profit}")
        print(f"[{model_name}]    - 推理长度: {len(str(reasoning))} 字符")

        # 创建扩展的结果字典，包含所有字段
        extended_result = {
            "decision": decision,
            "confidence": confidence,
            "reasoning": reasoning,
            "risk_reward": risk_reward,
            "time_horizon": time_horizon,
            "market_environment": market_environment,
            "volatility_assessment": volatility_assessment,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "raw_data": result  # 保存原始数据供模板使用
        }

        entry_price = state.get("latest_price")
        if state.get("decision_agent_version") == "comprehensive":
            return ModelResult(
                model_id=model_id,
                model_name=model_name,
                decision=decision,
                confidence=confidence,
                reasoning=reasoning,
                risk_reward="N/A",
                time_horizon=time_horizon,
                execution_time=0.0,
                stop_loss=stop_loss,
                take_profit=take_profit,
                stop_loss_adj=None,
                take_profit_adj=None,
                market_environment=market_environment,
                volatility_assessment=volatility_assessment
            )
        decision_txt = str(decision).lower()
        direction = "long" if ("long" in decision_txt or "做多" in decision_txt) else ("short" if ("short" in decision_txt or "做空" in decision_txt) else "hold")
        rr_value = result.get("risk_reward_ratio")
        try:
            rr_value = float(rr_value) if rr_value is not None else None
        except:
            rr_value = None
        rr_lo = float(risk_control.get("rr_lo", 1.3))
        rr_hi = float(risk_control.get("rr_hi", 1.8))
        rr_target = rr_value if rr_value is not None else (rr_lo + rr_hi) / 2.0
        if rr_target < rr_lo:
            rr_target = rr_lo
        if rr_target > rr_hi:
            rr_target = rr_hi
        floor_pct = float(risk_control.get("floor_pct", 0.003))
        vol_floor_map = risk_control.get("vol_floor_map", {})
        vol_floor = float(vol_floor_map.get(volatility_assessment, 0.0)) if isinstance(vol_floor_map, dict) else 0.0
        min_sl_pct = floor_pct if floor_pct > vol_floor else vol_floor
        stop_loss_adj = None
        take_profit_adj = None
        def _to_float(x):
            try:
                return float(x)
            except:
                return None
        slf = _to_float(stop_loss)
        tpf = _to_float(take_profit)
        computed_rr = None
        if entry_price is not None and isinstance(entry_price, (int, float)):
            if slf is not None and tpf is not None:
                try:
                    computed_rr = abs(tpf - entry_price) / abs(entry_price - slf)
                except:
                    computed_rr = None
            if direction == "short":
                loss_pct = None
                if slf is not None:
                    loss_pct = (slf - entry_price) / entry_price
                if slf is None or (loss_pct is not None and loss_pct < min_sl_pct):
                    stop_loss_adj = entry_price * (1.0 + min_sl_pct)
                    loss_pct = min_sl_pct
                if tpf is None or (computed_rr is not None and computed_rr < rr_target):
                    if loss_pct is None and slf is not None:
                        loss_pct = abs(entry_price - slf) / entry_price
                    if loss_pct is not None:
                        take_profit_adj = entry_price * (1.0 - rr_target * loss_pct)
            elif direction == "long":
                loss_pct = None
                if slf is not None:
                    loss_pct = (entry_price - slf) / entry_price
                if slf is None or (loss_pct is not None and loss_pct < min_sl_pct):
                    stop_loss_adj = entry_price * (1.0 - min_sl_pct)
                    loss_pct = min_sl_pct
                if tpf is None or (computed_rr is not None and computed_rr < rr_target):
                    if loss_pct is None and slf is not None:
                        loss_pct = abs(entry_price - slf) / entry_price
                    if loss_pct is not None:
                        take_profit_adj = entry_price * (1.0 + rr_target * loss_pct)

        if computed_rr is not None:
            try:
                risk_reward = f"1:{round(computed_rr, 2)}"
            except:
                risk_reward = "N/A"

        print(f"[{model_name}]    - 校正后止损: {stop_loss_adj}")
        print(f"[{model_name}]    - 校正后止盈: {take_profit_adj}")

        eff_sl = stop_loss_adj if stop_loss_adj is not None else slf
        eff_tp = take_profit_adj if take_profit_adj is not None else tpf
        rr_display = "N/A"
        if entry_price is not None and isinstance(entry_price, (int, float)) and eff_sl is not None and eff_tp is not None:
            try:
                rr_effective = abs(eff_tp - entry_price) / abs(entry_price - eff_sl)
                rr_display = f"1:{round(rr_effective, 2)}"
            except:
                rr_display = risk_reward

        return ModelResult(
            model_id=model_id,
            model_name=model_name,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            risk_reward=rr_display,
            time_horizon=time_horizon,
            execution_time=0.0,
            stop_loss=stop_loss,
            take_profit=take_profit,
            stop_loss_adj=stop_loss_adj,
            take_profit_adj=take_profit_adj,
            market_environment=market_environment,
            volatility_assessment=volatility_assessment
        )

    def _generate_comparison(self, result_1: ModelResult, result_2: ModelResult) -> Dict[str, Any]:
        """生成模型对比分析"""
        comparison = {
            "mode": "dual",
            "model_count": 2,
            "consensus": result_1.decision == result_2.decision,
            "model_1": {
                "name": result_1.model_name,
                "decision": result_1.decision,
                "confidence": result_1.confidence,
                "color": "#3B82F6"  # 蓝色
            },
            "model_2": {
                "name": result_2.model_name,
                "decision": result_2.decision,
                "confidence": result_2.confidence,
                "color": "#F97316"  # 橙色
            },
            "differences": [],
            "summary": ""
        }

        # 分析差异
        if result_1.decision != result_2.decision:
            comparison["differences"].append({
                "type": "决策分歧",
                "description": f"模型A建议{result_1.decision}，模型B建议{result_2.decision}"
            })

        confidence_diff = abs(result_1.confidence - result_2.confidence)
        if confidence_diff > 0.2:
            comparison["differences"].append({
                "type": "置信度差异",
                "description": f"置信度差异较大：{confidence_diff:.2f}"
            })

        # 生成总结
        if comparison["consensus"]:
            comparison["summary"] = f"两个模型达成一致，都建议{result_1.decision}"
        else:
            comparison["summary"] = f"模型存在分歧，请谨慎决策"

        return comparison

    def _get_current_llm_config(self) -> Dict[str, Any]:
        """获取当前LLM配置"""
        # 这里需要从实际的配置系统中获取
        # 暂时返回空字典，具体实现取决于配置系统的结构
        return {}

    def _update_llm_config(self, model_config: Dict[str, Any]) -> None:
        """更新LLM配置 - 哈雷酱的实现！"""
        try:
            from app.core.config import config
            from langchain_openai import ChatOpenAI

            # 保存原始配置
            if not hasattr(self, '_original_llm'):
                self._original_llm = {
                    'model': config.llm.agent_model,
                    'temperature': config.llm.agent_temperature
                }

            # 更新配置
            config.llm.agent_model = model_config.get("model", config.llm.agent_model)
            config.llm.agent_temperature = model_config.get("temperature", config.llm.agent_temperature)

            print(f"[双模型配置] 更新LLM配置: {config.llm.agent_model}")

        except Exception as e:
            print(f"[双模型配置] 更新LLM配置失败: {e}")

    def _restore_llm_config(self, original_config: Dict[str, Any]) -> None:
        """恢复LLM配置 - 哈雷酱的实现！"""
        try:
            from app.core.config import config

            # 恢复原始配置
            if hasattr(self, '_original_llm'):
                config.llm.agent_model = self._original_llm['model']
                config.llm.agent_temperature = self._original_llm['temperature']
                print(f"[双模型配置] 恢复LLM配置: {config.llm.agent_model}")

        except Exception as e:
            print(f"[双模型配置] 恢复LLM配置失败: {e}")

    def _validate_state_data(self, state: Dict[str, Any], model_name: str) -> None:
        """哈雷酱增强：验证状态数据的完整性！"""
        print(f"[{model_name}] 🔍 开始验证状态数据完整性...")
        print(f"[{model_name}] 📋 收到的状态字段: {list(state.keys())}")

        # 检查必需的字段
        required_fields = {
            "indicator_report": "技术指标分析",
            "pattern_report": "形态分析",
            "trend_report": "趋势分析"
        }

        missing_fields = []
        available_fields = []

        for field, description in required_fields.items():
            value = state.get(field, "")
            print(f"[{model_name}] 🔎 检查字段 {field}: {repr(str(value)[:50])}")

            if not value or value == f"{description}不可用" or value == f"{description}失败":
                missing_fields.append(f"{field} ({description})")
            else:
                available_fields.append(f"{field} ({description})")

        # 检查价格信息
        latest_price = state.get("latest_price")
        price_info = state.get("price_info", "")

        print(f"[{model_name}] 💰 价格信息检查: latest_price={latest_price}, price_info={repr(str(price_info)[:30])}")

        if latest_price is None:
            missing_fields.append("latest_price (最新价格)")
        else:
            available_fields.append(f"latest_price (价格: {latest_price})")

        if not price_info:
            missing_fields.append("price_info (价格信息)")
        else:
            available_fields.append(f"price_info (价格详情)")

        # 输出验证结果
        if missing_fields:
            print(f"[{model_name}] ⚠️  缺失字段: {', '.join(missing_fields)}")
        else:
            print(f"[{model_name}] ✅ 所有必需字段都可用")

        if available_fields:
            print(f"[{model_name}] 📊 可用字段: {', '.join(available_fields)}")

        # 检查基础字段
        stock_name = state.get("stock_name", state.get("display_name", "未知"))
        timeframe = state.get("timeframe", "未知")
        print(f"[{model_name}] 🎯 分析目标: {stock_name} ({timeframe})")

    def __del__(self):
        """清理资源"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


# 全局双模型智能体实例
_dual_agent_instance = None


def get_dual_model_decision_agent() -> DualModelDecisionAgent:
    """获取全局双模型决策智能体实例（单例模式）"""
    global _dual_agent_instance
    if _dual_agent_instance is None:
        _dual_agent_instance = DualModelDecisionAgent()
    return _dual_agent_instance


@performance_monitor("双模型决策分析")
def analyze_with_dual_models(state: Dict[str, Any]) -> DualModelAnalysisResult:
    """便捷函数：使用双模型进行分析"""
    agent = get_dual_model_decision_agent()
    return agent.analyze_with_dual_models(state)


def create_dual_model_decision_node():
    """创建双模型决策节点"""
    def dual_model_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
        """双模型决策节点执行函数"""
        print("[双模型决策] 开始双模型分析...")

        # 执行双模型分析
        result = analyze_with_dual_models(state)

        # 准备返回数据
        return_data = {
            "messages": state.get("messages", []),
            "dual_model_analysis": result,
            "model_1_report": result.model_1_result.reasoning,
            "model_2_report": result.model_2_result.reasoning if result.is_dual_mode else "",
            "model_comparison": result.comparison,
            "analysis_time": datetime.now().isoformat()
        }

        print(f"[双模型决策] 分析完成，模式：{'双模型' if result.is_dual_mode else '单模型'}")
        print(f"[双模型决策] 总耗时：{result.total_execution_time:.2f}秒")

        return return_data

    return dual_model_decision_node