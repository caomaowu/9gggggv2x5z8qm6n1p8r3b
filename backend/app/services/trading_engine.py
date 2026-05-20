from typing import Dict, Any, Optional
import logging
import pandas as pd
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.providers import get_provider_config
from app.core.graph_setup import SetGraph

logger = logging.getLogger(__name__)


def _build_action(direction: str) -> str:
    return {"long": "LONG", "short": "SHORT"}.get(direction, "HOLD")


def _build_decision_from_fusion(result: dict, latest_price: float | None, kline_open: float | None = None) -> dict:
    """Construct a frontend/backtest-compatible decision dict from brale Fusion output."""
    fusion = result.get("fusion_result") or {}
    indicator = result.get("indicator_summary") or {}
    structure = result.get("structure_summary") or {}
    mechanics = result.get("mechanics_summary") or {}

    direction = fusion.get("direction", "none")
    score = fusion.get("score", 0.0)
    confidence = fusion.get("confidence", 0.0)
    agreement = fusion.get("agreement", 0.0)
    resonance = fusion.get("resonance", {})
    agents = fusion.get("agents", {})

    action = _build_action(direction)
    entry_price = latest_price

    # Build evidence text
    evidence_parts = []
    if indicator.get("momentum_detail"):
        evidence_parts.append(f"[Indicator] {indicator['momentum_detail']}")
        if indicator.get("conflict_detail") and indicator["conflict_detail"] != "无明显冲突":
            evidence_parts.append(f"[Indicator冲突] {indicator['conflict_detail']}")
    if structure.get("volume_action"):
        evidence_parts.append(f"[Structure] regime={structure.get('regime')} break={structure.get('last_break')} vol={structure['volume_action']}")
    if mechanics.get("open_interest_context"):
        evidence_parts.append(f"[Mechanics] {mechanics['open_interest_context']}")
    reasoning = "\n".join(evidence_parts) if evidence_parts else f"Fusion: direction={direction} score={score:.2f}"

    # Signal type from score intensity
    if abs(score) > 0.7:
        signal_type = f"{direction.upper()}_STRONG"
    elif abs(score) > 0.35:
        signal_type = direction.upper()
    else:
        signal_type = "NEUTRAL"

    # Market environment from structure regime + indicator expansion
    regime = structure.get("regime", "unclear")
    expansion = indicator.get("expansion", "unknown")
    if regime in ("trend_up", "trend_down"):
        market_env = f"{regime} ({expansion})"
    else:
        market_env = f"{regime} (expansion={expansion})"

    # Volatility from ATR / expansion
    volatility = f"expansion={expansion} noise={indicator.get('noise', 'unknown')}"

    return {
        "action": action,
        "decision": action,
        "direction": direction,
        "score": round(score, 4),
        "confidence": round(confidence, 4),
        "confidence_level": f"{round(confidence * 100, 1)}%",
        "agreement": round(agreement, 4),
        "reasoning": reasoning,
        "justification": reasoning,
        "entry_point": entry_price,
        "kline_open": kline_open,
        "kline_close": latest_price,
        "stop_loss": None,
        "take_profit": None,
        "risk_reward_ratio": None,
        "forecast_horizon": "next 1-2 bars",
        "market_environment": market_env,
        "volatility_assessment": volatility,
        "signal_type": signal_type,
        "resonance": resonance,
        "agent_scores": agents,
        "fusion_raw": fusion,
    }


class TradingEngine:
    """
    brale-core trading analysis engine.
    Pipeline: compress → 3 parallel LLM agents → consensus fusion → decision output.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        override_indicator_model = None
        override_structure_model = None
        override_mechanics_model = None
        override_indicator_temp = None
        override_structure_temp = None
        override_mechanics_temp = None

        if config:
            override_indicator_model = config.get("indicator_llm_model")
            override_structure_model = config.get("structure_llm_model")
            override_mechanics_model = config.get("mechanics_llm_model")
            override_indicator_temp = config.get("indicator_llm_temperature")
            override_structure_temp = config.get("structure_llm_temperature")
            override_mechanics_temp = config.get("mechanics_llm_temperature")

        self.indicator_llm = self._create_brale_llm(
            "indicator", override_indicator_model, override_indicator_temp,
            default_temp=getattr(settings, 'BRALE_INDICATOR_TEMPERATURE', 0.2),
        )
        self.structure_llm = self._create_brale_llm(
            "structure", override_structure_model, override_structure_temp,
            default_temp=getattr(settings, 'BRALE_STRUCTURE_TEMPERATURE', 0.1),
        )
        self.mechanics_llm = self._create_brale_llm(
            "mechanics", override_mechanics_model, override_mechanics_temp,
            default_temp=getattr(settings, 'BRALE_MECHANICS_TEMPERATURE', 0.2),
        )

        self.graph_setup = SetGraph(
            self.indicator_llm,
            self.structure_llm,
            self.mechanics_llm,
        )
        self.graph = self.graph_setup.set_graph()

    def _create_brale_llm(self, agent_name: str, model: str | None, temperature: float | None,
                          default_temp: float) -> ChatOpenAI:
        provider_attr = f"BRALE_{agent_name.upper()}_PROVIDER"
        model_attr = f"BRALE_{agent_name.upper()}_MODEL"

        provider = getattr(settings, provider_attr, None) or settings.AGENT_PROVIDER
        default_model = getattr(settings, model_attr, None) or settings.AGENT_MODEL

        actual_model = model or default_model
        actual_temp = temperature if temperature is not None else default_temp

        cfg = get_provider_config(provider)
        if not cfg:
            raise ValueError(f"Unknown provider: {provider}")

        api_key = getattr(settings, cfg["api_key_env"], "")
        if not api_key:
            raise ValueError(f"API Key not found for provider {provider}. Set {cfg['api_key_env']} in .env")

        return ChatOpenAI(
            model=actual_model,
            api_key=api_key,
            base_url=cfg["base_url"],
            temperature=actual_temp,
            request_timeout=settings.LLM_TIMEOUT,
            max_retries=3,
            streaming=False,
        )

    async def run_analysis(self, data: Any, symbol: str, timeframe: str,
                           derivative_data: dict | None = None) -> Dict[str, Any]:
        import json

        is_multi_tf = isinstance(data, dict) and not hasattr(data, 'to_dict')
        latest_price = None
        kline_open = None

        if is_multi_tf:
            first_tf = list(data.keys())[0]
            first_df = data[first_tf]
            if isinstance(first_df, pd.DataFrame) and not first_df.empty and 'Close' in first_df.columns:
                latest_price = float(first_df['Close'].iloc[-1])
            if isinstance(first_df, pd.DataFrame) and not first_df.empty and 'Open' in first_df.columns:
                kline_open = float(first_df['Open'].iloc[-1])
        elif isinstance(data, pd.DataFrame):
            if not data.empty and 'Close' in data.columns:
                latest_price = float(data['Close'].iloc[-1])
            if not data.empty and 'Open' in data.columns:
                kline_open = float(data['Open'].iloc[-1])

        initial_state = {
            "kline_data": data,
            "time_frame": timeframe,
            "stock_name": symbol,
            "messages": [],
            "latest_price": latest_price,
            "kline_open": kline_open,
            "multi_timeframe_mode": is_multi_tf,
            "timeframes": list(data.keys()) if is_multi_tf else None,
            "derivative_data": derivative_data or {},
            "mechanics_compressed": None,      # filled by compress_coordinator
            "indicator_compressed": None,       # filled by compress_coordinator
            "structure_compressed": None,       # filled by compress_coordinator
        }

        try:
            import asyncio
            result = await asyncio.to_thread(self.graph.invoke, initial_state)

            if "error" not in result:
                # Build decision from Fusion (replaces old Decision Agent)
                result["decision"] = _build_decision_from_fusion(result, latest_price, kline_open)

                fusion = result.get("fusion_result") or {}
                indicator_sum = result.get("indicator_summary") or {}
                structure_sum = result.get("structure_summary") or {}
                mechanics_sum = result.get("mechanics_summary") or {}

                result["market_data"] = {
                    "analysis": {
                        "indicators": json.dumps(indicator_sum, ensure_ascii=False, indent=2),
                        "structure": json.dumps(structure_sum, ensure_ascii=False, indent=2),
                        "mechanics": json.dumps(mechanics_sum, ensure_ascii=False, indent=2),
                    },
                    "fusion": fusion,
                    "indicator_summary": indicator_sum,
                    "structure_summary": structure_sum,
                    "mechanics_summary": mechanics_sum,
                }

                logger.info(
                    "[brale] Analysis: direction=%s score=%.3f conf=%.3f",
                    fusion.get("direction"), fusion.get("score", 0), fusion.get("confidence", 0),
                )

            return result
        except Exception as e:
            logger.exception("[brale] Analysis failed")
            return {"error": f"Analysis failed: {str(e)}", "messages": []}
