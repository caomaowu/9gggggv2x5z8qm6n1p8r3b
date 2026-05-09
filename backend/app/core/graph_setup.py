from typing import Dict
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import sys
import io
import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agents.agent_state import IndicatorAgentState

# brale-core agents
from app.agents.brale_indicator_agent import create_brale_indicator_agent
from app.agents.brale_structure_agent import create_brale_structure_agent
from app.agents.brale_mechanics_agent import create_brale_mechanics_agent

# brale-core preprocessing
from app.agents.preprocessing.indicator_compress import compress_indicator
from app.agents.preprocessing.structure_compress import compress_structure
from app.agents.preprocessing.mechanics_compress import compress_mechanics
from app.agents.preprocessing.fusion import compute_consensus


class SetGraph:
    def __init__(
        self,
        indicator_llm,
        structure_llm,
        mechanics_llm,
    ):
        self.indicator_llm = indicator_llm
        self.structure_llm = structure_llm
        self.mechanics_llm = mechanics_llm

    def set_graph(self):
        indicator_node = create_brale_indicator_agent(self.indicator_llm)
        structure_node = create_brale_structure_agent(self.structure_llm)
        mechanics_node = create_brale_mechanics_agent(self.mechanics_llm)

        def compress_coordinator(state):
            print("[brale] Compress coordinator: preprocessing data...")

            shared = state.copy()
            kline_data = state.get("kline_data", {})
            symbol = state.get("stock_name", "")
            interval = state.get("time_frame", "1H")
            derivative_data = state.get("derivative_data") or {}
            multi_tf = state.get("multi_timeframe_mode", False)

            import pandas as pd

            def _ensure_df(data):
                if isinstance(data, pd.DataFrame):
                    return data
                if isinstance(data, dict):
                    try:
                        return pd.DataFrame(data)
                    except Exception:
                        return None
                return None

            if multi_tf and isinstance(kline_data, dict):
                primary_tf = interval
                if primary_tf in kline_data:
                    df = _ensure_df(kline_data[primary_tf])
                    indicator_compressed = {}
                    structure_compressed = {}
                    for tf, data in kline_data.items():
                        tf_df = _ensure_df(data)
                        if tf_df is None:
                            continue
                        try:
                            indicator_compressed[tf] = compress_indicator(tf_df, tf, symbol)
                        except Exception as e:
                            print(f"[brale] Indicator compress failed for {tf}: {e}")
                        try:
                            structure_compressed[tf] = compress_structure(tf_df, tf, symbol)
                        except Exception as e:
                            print(f"[brale] Structure compress failed for {tf}: {e}")
                    shared["indicator_compressed"] = indicator_compressed.get(primary_tf) if indicator_compressed else None
                    shared["structure_compressed"] = structure_compressed.get(primary_tf) if structure_compressed else None
                    shared["indicator_compressed_all"] = indicator_compressed
                    shared["structure_compressed_all"] = structure_compressed
                    print(f"[brale] Multi-TF compressed: {list(indicator_compressed.keys())}")
                else:
                    df = None
            else:
                df = _ensure_df(kline_data)

            if df is None or df.empty:
                print("[brale] WARNING: empty/unusable DataFrame")
                return shared

            col_map = {c.lower(): c for c in df.columns}
            for std in ["open", "high", "low", "close", "volume"]:
                if std in col_map and col_map[std] != std.capitalize():
                    df = df.rename(columns={col_map[std]: std.capitalize()})

            if not multi_tf or not isinstance(kline_data, dict):
                try:
                    shared["indicator_compressed"] = compress_indicator(df, interval, symbol)
                    print("[brale] Indicator compressed OK")
                except Exception as e:
                    print(f"[brale] Indicator compress failed: {e}")
                try:
                    shared["structure_compressed"] = compress_structure(df, interval, symbol)
                    print("[brale] Structure compressed OK")
                except Exception as e:
                    print(f"[brale] Structure compress failed: {e}")

            try:
                mech_df = df
                if multi_tf and isinstance(kline_data, dict) and interval in kline_data:
                    mech_df = _ensure_df(kline_data[interval]) or df
                shared["mechanics_compressed"] = compress_mechanics(
                    ohlcv_data=mech_df,
                    oi_snapshot=derivative_data.get("oi"),
                    oi_history=derivative_data.get("oi_history"),
                    funding_history=derivative_data.get("funding_history"),
                    long_short_history=derivative_data.get("long_short_history"),
                    taker_volume_history=derivative_data.get("taker_volume_history"),
                    liquidation_orders=derivative_data.get("liquidation_orders"),
                    symbol=symbol, interval=interval,
                )
                print("[brale] Mechanics compressed OK")
            except Exception as e:
                print(f"[brale] Mechanics compress failed: {e}")

            return shared

        def brale_agent_coordinator(state):
            print("[brale] Launching 3 analysis agents in parallel...")
            shared = state.copy()
            results = {}

            def run_agent(name, node_fn):
                print(f"[brale] Running {name} agent...")
                try:
                    result = node_fn(shared)
                    results[name] = result
                    print(f"[brale] {name} agent done")
                except Exception as e:
                    print(f"[brale] {name} agent FAILED: {e}")
                    results[name] = {"error": str(e)}

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(run_agent, "indicator", indicator_node),
                    executor.submit(run_agent, "structure", structure_node),
                    executor.submit(run_agent, "mechanics", mechanics_node),
                ]
                for f in futures:
                    f.result()

            for name, result in results.items():
                key_map = {
                    "indicator": "indicator_summary",
                    "structure": "structure_summary",
                    "mechanics": "mechanics_summary",
                }
                out_key = key_map.get(name)
                if out_key and out_key in result and result[out_key] is not None:
                    shared[out_key] = result[out_key]

            return shared

        def fusion_node(state):
            print("[brale] Computing consensus fusion...")
            result = compute_consensus(
                indicator_summary=state.get("indicator_summary"),
                structure_summary=state.get("structure_summary"),
                mechanics_summary=state.get("mechanics_summary"),
            )
            print(f"[brale] Fusion: direction={result['direction']} score={result['score']} conf={result['confidence']}")
            return {"fusion_result": result}

        graph = StateGraph(IndicatorAgentState)
        graph.add_node("compress", compress_coordinator)
        graph.add_node("agents", brale_agent_coordinator)
        graph.add_node("fusion", fusion_node)

        graph.add_edge(START, "compress")
        graph.add_edge("compress", "agents")
        graph.add_edge("agents", "fusion")
        graph.add_edge("fusion", END)

        return graph.compile()
