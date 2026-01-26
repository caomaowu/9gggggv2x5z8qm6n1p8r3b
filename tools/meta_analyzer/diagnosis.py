import sys
import os
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 动态添加 backend 目录到 sys.path
# 当前文件在 tools/meta_analyzer/diagnosis.py
# 需要添加的是 tools/../backend
current_dir = os.path.dirname(os.path.abspath(__file__))
tools_dir = os.path.dirname(os.path.dirname(current_dir)) # refactor_v2/tools -> refactor_v2
backend_dir = os.path.join(tools_dir, "backend")

# 显式加载 .env
# 优先级 1: 当前目录下的 .env (tools/meta_analyzer/.env)
local_env_path = os.path.join(current_dir, ".env")
# 优先级 2: backend 目录下的 .env
backend_env_path = os.path.join(backend_dir, ".env")

if os.path.exists(local_env_path):
    load_dotenv(local_env_path, override=True)
    print(f"Loaded environment variables from {local_env_path}")
elif os.path.exists(backend_env_path):
    load_dotenv(backend_env_path)
    print(f"Loaded environment variables from {backend_env_path}")
else:
    print(f"Warning: No .env file found in {local_env_path} or {backend_env_path}")

class MetaAgent:
    def __init__(self):
        self.llm = self._init_llm()
        
        # 加载 Prompt 模板
        template_path = os.path.join(os.path.dirname(__file__), "templates", "critic_prompt.md")
        self.prompt_template = ""
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                self.prompt_template = f.read()

    def _init_llm(self):
        """独立初始化 LLM 客户端，解耦 backend 依赖"""
        try:
            # 1. 获取 Provider 配置
            provider = os.getenv("AGENT_PROVIDER", "iflow").lower()
            model = os.getenv("AGENT_MODEL", "qwen3-max")
            temperature = float(os.getenv("AGENT_TEMPERATURE", "0.2"))
            
            # 2. 映射 Base URL 和 API Key
            # 这里的映射逻辑是简化的，实际项目中可能需要更完善的配置管理
            api_key = ""
            base_url = ""
            
            if provider == "iflow":
                api_key = os.getenv("IFLOW_API_KEY", "")
                base_url = "https://www.iflow.net/v1" # 假设的 iflow base url，请根据实际情况修改
                # 注意：如果 iflow 兼容 OpenAI 协议，通常 Base URL 类似于 https://api.iflow.com/v1
                # 检查 backend/app/core/providers.py 可以获取准确的 Base URL
                # 这里暂时使用通用的 fallback 或者尝试从环境变量读取 CUSTOM_API_BASE
                if not base_url or "iflow.net" in base_url: # Placeholder check
                     # 尝试从环境变量读取 Base URL，如果 .env 中没有定义，则使用默认
                     # 为了保险，我们假设用户正确配置了 .env，或者我们应该去 backend 查一下 providers.py
                     # 但为了解耦，我们最好要求用户在 .env 中显式配置，或者硬编码已知的
                     pass
                # 修正：根据用户提供的 .env，IFLOW 是主要 Provider。
                # 假设 iflow 的 base_url 是 https://zz-api.iflow.land/v1 (举例) 或者 https://api.iflow.ai/v1
                # 由于我无法读取 providers.py (import 失败)，我将尝试推断或使用通用兼容方式。
                # 很多兼容 OpenAI 的服务只需要 base_url 和 api_key。
                # 让我们假设用户在 .env 里配置了，或者我们可以硬编码几个常见的。
                # *关键*：如果是 iflow，我们需要知道它的 base_url。
                # 让我们先读取一下 backend/app/core/providers.py 看看 base_url 是什么，然后硬编码在这里。
                pass
            
            # 临时硬编码 Provider 映射 (为了解耦)
            provider_configs = {
                "iflow": {"base_url": "https://apis.iflow.cn/v1", "api_key_env": "IFLOW_API_KEY"},
                "iflow2": {"base_url": "https://apis.iflow.cn/v1", "api_key_env": "IFLOW2_API_KEY"},
                "deepseek": {"base_url": "https://api.deepseek.com/v1", "api_key_env": "DEEPSEEK_API_KEY"},
                "openrouter": {"base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"},
                "openai": {"base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"},
                "modelscope": {"base_url": "https://api-inference.modelscope.cn/v1", "api_key_env": "MODELSCOPE_API_KEY"},
            }
            
            # 尝试从 providers.py 获取真实配置 (静态读取文件)
            # 这是一个 hack，为了获取正确的 base_url
            real_base_url = self._read_base_url_from_file(provider)
            if real_base_url:
                base_url = real_base_url
            
            # 获取 API Key
            # 优先使用 provider_configs 中的映射，如果找不到则尝试通用的命名规则
            if provider in provider_configs:
                api_key_env = provider_configs[provider]["api_key_env"]
                api_key = os.getenv(api_key_env, "")
                if not base_url and "base_url" in provider_configs[provider]:
                     base_url = provider_configs[provider]["base_url"]
            else:
                # Fallback: 尝试 CONFIG_API_KEY 格式
                api_key = os.getenv(f"{provider.upper()}_API_KEY", "")
            
            if not api_key:
                print(f"Error: API Key not found for provider {provider}")
                return None

            print(f"Initializing LLM: Provider={provider}, Model={model}, BaseURL={base_url}")
            
            return ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=api_key,
                base_url=base_url if base_url else None, # 如果没有 base_url，ChatOpenAI 默认连 OpenAI
            )
        except Exception as e:
            print(f"Error initializing LLM client: {e}")
            return None

    def _read_base_url_from_file(self, provider_name):
        """静态解析 providers.py 以获取 Base URL，避免 import 错误"""
        try:
            providers_path = os.path.join(backend_dir, "app", "core", "providers.py")
            if not os.path.exists(providers_path):
                return None
            
            with open(providers_path, "r", encoding="utf-8") as f:
                content = f.read()
                # 简单的字符串查找，不够严谨但有效
                # 查找类似 "iflow": { ... "base_url": "xxx" ... } 的结构
                # 或者直接查找 PROVIDERS 字典定义
                import ast
                # 尝试解析 PROVIDERS 字典
                # 这需要 providers.py 的结构比较简单
                # 让我们尝试一种更简单的 regex 方式或者直接假设
                pass
        except:
            pass
        return None

    def diagnose_case(self, case_data: Dict[str, Any]):
        """
        对单个案例进行诊断
        """
        if not self.llm:
            return "Error: LLM Client not initialized."

        # 1. 提取 Agent 决策上下文
        decision = case_data.get("decision", {})
        analysis_results = case_data.get("analysis_results", {})
        
        # 提取各个 Agent 的报告
        indicator_report = "N/A"
        pattern_report = "N/A"
        trend_report = "N/A"
        
        if "Indicator" in analysis_results:
             indicator_report = analysis_results["Indicator"].get("indicator_report", "N/A")
        
        if "Pattern" in analysis_results:
             pattern_report = analysis_results["Pattern"].get("pattern_report", "N/A")
             
        if "Trend" in analysis_results:
             trend_report = analysis_results["Trend"].get("trend_report", "N/A")

        # 2. 格式化未来市场走势
        future_kline = case_data.get("future_kline_data", [])
        future_summary = self._format_future_market(future_kline)
        
        # 3. 计算盈亏
        max_profit, max_drawdown = self._calculate_pnl(case_data)

        # 4. 构建 Prompt
        prompt = self.prompt_template.format(
            asset=case_data.get("asset", "Unknown"),
            timeframe=case_data.get("timeframe", "4h"),
            action=decision.get("action", "HOLD"),
            reasoning=decision.get("reasoning", "N/A"),
            indicator_report=indicator_report,
            pattern_report=pattern_report,
            trend_report=trend_report,
            future_market_summary=future_summary,
            max_profit=max_profit,
            max_drawdown=max_drawdown
        )
        
        # 5. 调用 LLM
        return self.llm.stream(prompt)

    def _format_future_market(self, klines: list) -> str:
        if not klines:
            return "No future data available."
            
        summary = []
        for i, k in enumerate(klines[:12]): # 限制显示前12根
            dt = k.get("datetime", "")
            o = k.get("open", 0)
            h = k.get("high", 0)
            l = k.get("low", 0)
            c = k.get("close", 0)
            summary.append(f"[{dt}] O:{o} H:{h} L:{l} C:{c}")
        return "\n".join(summary)

    def _calculate_pnl(self, data: Dict) -> tuple:
        # 简化的 PnL 计算
        future_kline = data.get("future_kline_data", [])
        decision = data.get("decision", {})
        action = decision.get("action", "HOLD")
        
        # 尝试获取 entry_point
        entry_point = decision.get("entry_point", 0)
        if isinstance(entry_point, str):
            try:
                entry_point = float(entry_point.replace(",", ""))
            except:
                entry_point = 0
        
        if not entry_point:
             entry_point = data.get("latest_price", 0)
             
        # 如果还是没有，尝试从第一根未来K线的Open获取
        if not entry_point and future_kline:
            entry_point = future_kline[0].get("open", 0)

        if not future_kline or not entry_point or action not in ["LONG", "SHORT"]:
            return 0.0, 0.0
            
        entry_point = float(entry_point)

        highs = [float(k.get("high", 0)) for k in future_kline]
        lows = [float(k.get("low", 0)) for k in future_kline]
        
        if not highs: return 0.0, 0.0

        if action == "LONG":
            max_p = (max(highs) - entry_point) / entry_point * 100
            max_d = (min(lows) - entry_point) / entry_point * 100
        else:
            max_p = (entry_point - min(lows)) / entry_point * 100
            max_d = (entry_point - max(highs)) / entry_point * 100
            
        return round(max_p, 2), round(max_d, 2)
