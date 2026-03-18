import argparse
import csv
import hashlib
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Setup paths and environment
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from dotenv import load_dotenv

# Load .env variables before anything else
env_path = backend_dir / ".env"
load_dotenv(env_path)

from app.agents.decision.decision_agent_original import ORIGINAL_PROMPT_TEMPLATE
from app.core.config import create_optimizer_llm, reload_config, settings
from app.utils.llm_compat import stream_llm_text
from tools.prompt_tuning.prompt_tuning_engine import (
    BatchBacktestRunner,
    BatchRunConfig,
    BatchRunSummary,
)

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("AutoOptimizer")

RUN_SUMMARY_FIELDNAMES = [
    "本次运行开始时间",
    "世代",
    "记录时间",
    "Prompt版本",
    "Prompt哈希",
    "决策模型供应商",
    "决策模型",
    "分析模型供应商",
    "分析模型",
    "优化模型供应商",
    "优化模型",
    "总样本数",
    "成功数",
    "回测跳过数",
    "失败数",
    "加载失败数",
    "LLM失败数",
    "解析失败数",
    "K1胜率",
    "K1胜利数",
    "K2胜率",
    "K2胜利数",
    "解析率",
    "LONG数量",
    "SHORT数量",
    "HOLD数量",
    "多空比",
    "当时是否最佳",
    "导出目录",
]


def _preview_text(text: str, max_chars: int = 600) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"


@dataclass
class OptimizationRecord:
    generation: int
    timestamp: str
    prompt_content: str
    prompt_hash: str

    # Metrics
    total_trades: int
    win_rate: float
    k1_win_rate: float
    k1_win_count: int
    k2_win_rate: float
    k2_win_count: int
    long_count: int
    short_count: int
    long_short_ratio: float
    parse_rate: float

    # Optimizer's thoughts
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OptimizationRecord":
        return cls(**data)


class OptimizationHistory:
    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.records: List[OptimizationRecord] = []
        self._load()

    def _load(self):
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        self.records.append(OptimizationRecord.from_dict(item))
                logger.info(f"Loaded {len(self.records)} records from {self.history_file.name}")
            except Exception as e:
                logger.error(f"Failed to load history from {self.history_file}: {e}")

    def save(self):
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(
                [r.to_dict() for r in self.records], f, ensure_ascii=False, indent=2
            )

    def add_record(self, record: OptimizationRecord):
        self.records.append(record)
        self.save()

    def get_best_record(self) -> Optional[OptimizationRecord]:
        if not self.records:
            return None
        # Maximize win_rate, tie break with parse_rate
        return max(self.records, key=lambda r: (r.win_rate, r.parse_rate, r.total_trades))

    def get_latest_generation(self) -> int:
        if not self.records:
            return 0
        return max(r.generation for r in self.records)


class AutoOptimizer:
    def __init__(self, data_dir: str, work_dir: str):
        self.data_dir = Path(data_dir).resolve()
        self.work_dir = Path(work_dir).resolve()
        self.history_file = self.work_dir / "optimization_history.json"
        self.evaluator_provider = settings.AGENT_PROVIDER
        self.evaluator_model = settings.AGENT_MODEL
        self.analysis_provider = settings.GRAPH_PROVIDER
        self.analysis_model = settings.GRAPH_MODEL
        self.optimizer_provider = settings.OPTIMIZER_PROVIDER
        self.optimizer_model = settings.OPTIMIZER_MODEL

        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.history = OptimizationHistory(self.history_file)
        self.runner = BatchBacktestRunner()
        self.llm = create_optimizer_llm()

    def _export_run_summary_csv(self, records: List[Dict[str, Any]]) -> Optional[Path]:
        if not records:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = self.work_dir / f"optimization_run_summary_{timestamp}.csv"
        with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=RUN_SUMMARY_FIELDNAMES)
            writer.writeheader()
            for record in records:
                writer.writerow(record)
        return csv_path

    def _generate_meta_prompt(self, current_prompt: str) -> str:
        """
        Build a meta-prompt that includes historical generations to guide the LLM
        to produce a better Prompt.
        """
        history_text = ""
        # Keep last 5 generations to avoid context overflow, but ensure best is considered
        recent_records = self.history.records[-5:]
        for r in recent_records:
            history_text += f"=== Generation {r.generation} ===\n"
            history_text += (
                f"K1 Win Rate: {r.k1_win_rate:.2%} "
                f"(price basepoint + the 1st same-timeframe candle, wins: {r.k1_win_count})\n"
            )
            history_text += (
                f"K2 Win Rate: {r.k2_win_rate:.2%} "
                f"(price basepoint + the 2nd same-timeframe candle, wins: {r.k2_win_count})\n"
            )
            history_text += f"Parse Rate: {r.parse_rate:.2%}\n"
            history_text += f"Reasoning for this prompt:\n{r.reasoning}\n\n"

        best_record = self.history.get_best_record()
        best_text = ""
        if best_record:
            best_text = (
                f"The BEST performing prompt so far achieved a K1 Win Rate of {best_record.k1_win_rate:.2%} "
                f"and a K2 Win Rate of {best_record.k2_win_rate:.2%} in Generation {best_record.generation}.\n"
            )

        meta_prompt = f"""You are an expert AI Prompt Engineer and Trading Strategy Optimizer.
Your task is to iteratively optimize the System Prompt for an Evaluator LLM that predicts short-term cryptocurrency price movements based on technical analysis.

Metric definitions:
- K1 Win Rate: the hit rate on the 1st same-timeframe candle after the price basepoint.
- K2 Win Rate: the hit rate on the 2nd same-timeframe candle after the price basepoint.
- K1 is the primary metric. K2 is a secondary metric.

The Evaluator LLM MUST ALWAYS output a valid JSON block containing a "decision" field. The decision MUST be exactly one of: "LONG", "SHORT", or "HOLD".
Example:
```json
{{
  "decision": "LONG",
  "confidence": 0.85,
  "reasoning": "..."
}}
```

Here is the historical performance of previous prompt generations:
{best_text}

[Recent History]
{history_text}

[Current Prompt to Optimize]
{current_prompt}

Your objective:
1. Maximize K1 Win Rate first.
2. Improve K2 Win Rate when possible, but do not sacrifice K1 unnecessarily.
3. Ensure the Parse Rate is 100% (the Evaluator must output valid JSON).
4. The new prompt MUST use the following variables as placeholders:
   {{stock_name}}, {{time_frame}}, {{price_summary}}, {{price_info_str}}, {{latest_price_str}}, {{indicator_report}}, {{pattern_report}}, {{trend_report}}.
   (Do NOT replace these placeholders with real values. Keep them as bracketed variables).

Analyze the recent history and the Current Prompt. Identify weaknesses and formulate an improved prompt. 

OUTPUT FORMAT:
1. Provide your reasoning and analysis first.
2. Then, provide the entirely new prompt template enclosed in <prompt> and </prompt> tags.

Go ahead and generate the reasoning and the new prompt.
"""
        return meta_prompt

    def _parse_optimizer_response(self, response_text: str) -> tuple[str, str]:
        """
        Extract reasoning and the new prompt from the LLM's response.
        """
        prompt_match = re.search(r"<prompt>(.*?)</prompt>", response_text, re.DOTALL)
        if prompt_match:
            prompt_content = prompt_match.group(1).strip()
            reasoning = response_text.replace(prompt_match.group(0), "").strip()
            return reasoning, prompt_content

        return "Failed to extract reasoning", ""

    def run_evolution_loop(self, max_generations: int = 10, concurrency: int = 3, cancel_event=None, event_callback=None):
        logger.info(f"Starting Auto-Optimizer for up to {max_generations} generations.")
        logger.info(f"Data Dir: {self.data_dir}")
        logger.info(f"Work Dir: {self.work_dir}")

        if event_callback:
            event_callback(
                {
                    "type": "optimizer_log",
                    "message": (
                        f"Starting Auto-Optimizer for up to {max_generations} generations.\n"
                        f" - Data Dir: {self.data_dir}\n"
                        f" - Work Dir: {self.work_dir}\n"
                        f" - Concurrency: {concurrency}"
                    ),
                }
            )

        start_generation = self.history.get_latest_generation() + 1
        run_started_at = datetime.now().astimezone().isoformat(timespec="seconds")
        current_run_records: List[Dict[str, Any]] = []
        run_summary_csv_path: Optional[Path] = None
        
        # Determine starting prompt
        if start_generation == 1:
            current_prompt = ORIGINAL_PROMPT_TEMPLATE
            reasoning = "Initial Baseline Prompt from System"
        else:
            latest_record = self.history.records[-1]
            current_prompt = latest_record.prompt_content
            reasoning = "Continuing from the previous run"

        # Loop
        for gen in range(start_generation, start_generation + max_generations):
            if cancel_event and cancel_event.is_set():
                logger.info("Evolution loop cancelled by user.")
                if event_callback:
                    event_callback({"type": "optimizer_log", "message": "Evolution loop cancelled by user."})
                break

            logger.info(f"\n{'='*40}")
            logger.info(f"=== Starting Generation {gen} ===")
            logger.info(f"{'='*40}")
            if event_callback:
                event_callback({"type": "optimizer_log", "message": f"=== Starting Generation {gen} ==="})
                event_callback({"type": "optimizer_gen_start", "generation": gen})

            prompt_hash = hashlib.md5(current_prompt.encode("utf-8")).hexdigest()[:8]
            prompt_version = f"gen_{gen}_{prompt_hash}"
            if event_callback:
                event_callback(
                    {
                        "type": "optimizer_prompt_snapshot",
                        "generation": gen,
                        "stage": "current",
                        "prompt_version": prompt_version,
                        "prompt_hash": prompt_hash,
                        "prompt_chars": len(current_prompt),
                        "preview": _preview_text(current_prompt),
                    }
                )

            export_dir = self.work_dir / f"gen_{gen}"
            config = BatchRunConfig(
                input_dir=str(self.data_dir),
                prompt_template=current_prompt,
                prompt_version=prompt_version,
                export_dir=str(export_dir),
                concurrency=concurrency,
            )

            # --- Step 1: Evaluate Current Prompt ---
            logger.info(f"Evaluating prompt (version: {prompt_version})...")
            if event_callback:
                event_callback({"type": "optimizer_log", "message": f"Evaluating prompt (version: {prompt_version})..."})
            
            # Use silent event callback to avoid spamming the console too much
            def on_event(event: Dict[str, Any]):
                if event_callback:
                    # Rename batch event types so they don't interfere with the main GUI's standalone batch state
                    if event["type"] in ["batch_started", "file_started", "file_completed", "batch_completed", "batch_failed"]:
                        evt_copy = dict(event)
                        evt_copy["type"] = f"opt_{event['type']}"
                        event_callback(evt_copy)
                    else:
                        event_callback(event)
                
                if event["type"] == "batch_completed":
                    s = event["summary"]
                    logger.info(f"Batch completed. Total: {s['total']}, Succeeded: {s['succeeded']}, Failed: {s['failed']}")
                elif event["type"] == "file_completed":
                    if event["processed_count"] % 10 == 0:
                        logger.info(f"Progress: {event['processed_count']}/{event['submitted_count']}")

            summary, _ = self.runner.run(config, cancel_event=cancel_event, event_callback=on_event)

            total = summary.total
            if total == 0:
                logger.error("No test data found in the data directory! Aborting.")
                break

            parse_rate = (summary.succeeded + summary.backtest_skipped) / total if total > 0 else 0.0
            win_rate = summary.k1_win_rate
            short_count = summary.short_count
            long_short_ratio = summary.long_count / short_count if short_count > 0 else float("inf")

            logger.info(f"Generation {gen} Results:")
            logger.info(f" - K1 Win Rate: {summary.k1_win_rate:.2%}")
            logger.info(f" - K2 Win Rate: {summary.k2_win_rate:.2%}")
            logger.info(f" - Parse Rate: {parse_rate:.2%}")
            logger.info(f" - L/S Ratio: {long_short_ratio:.2f} (L:{summary.long_count}, S:{short_count}, H:{summary.hold_count})")
            if event_callback:
                event_callback({
                    "type": "optimizer_log", 
                    "message": (
                        f"Generation {gen} Results:\n"
                        f" - K1 Win Rate: {summary.k1_win_rate:.2%} ({summary.k1_win_count} wins)\n"
                        f" - K2 Win Rate: {summary.k2_win_rate:.2%} ({summary.k2_win_count} wins)\n"
                        f" - Parse Rate: {parse_rate:.2%}\n"
                        f" - L/S Ratio: {long_short_ratio:.2f}\n"
                        f" - Trades: total={summary.total}, success={summary.succeeded}, skipped={summary.backtest_skipped}, failed={summary.failed}\n"
                        f" - Execution Failures: load={summary.load_failed}, llm={summary.llm_failed}, parse={summary.parse_failed}\n"
                        f" - Decisions: LONG={summary.long_count}, SHORT={summary.short_count}, HOLD={summary.hold_count}\n"
                        f" - K1: {summary.k1_win_rate:.2%} ({summary.k1_win_count} wins)\n"
                        f" - K2: {summary.k2_win_rate:.2%} ({summary.k2_win_count} wins)\n"
                        f" - Export Dir: {export_dir}"
                    )
                })
                event_callback(
                    {
                        "type": "optimizer_gen_metrics",
                        "generation": gen,
                        "prompt_version": prompt_version,
                        "prompt_hash": prompt_hash,
                        "export_dir": str(export_dir),
                        "win_rate": win_rate,
                        "parse_rate": parse_rate,
                        "ls_ratio": long_short_ratio,
                        "total": summary.total,
                        "succeeded": summary.succeeded,
                        "failed": summary.failed,
                        "backtest_skipped": summary.backtest_skipped,
                        "load_failed": summary.load_failed,
                        "llm_failed": summary.llm_failed,
                        "parse_failed": summary.parse_failed,
                        "long_count": summary.long_count,
                        "short_count": summary.short_count,
                        "hold_count": summary.hold_count,
                        "k1_win_rate": summary.k1_win_rate,
                        "k1_win_count": summary.k1_win_count,
                        "k2_win_rate": summary.k2_win_rate,
                        "k2_win_count": summary.k2_win_count,
                    }
                )

            # Save to History
            record = OptimizationRecord(
                generation=gen,
                timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
                prompt_content=current_prompt,
                prompt_hash=prompt_hash,
                total_trades=total,
                win_rate=win_rate,
                k1_win_rate=summary.k1_win_rate,
                k1_win_count=summary.k1_win_count,
                k2_win_rate=summary.k2_win_rate,
                k2_win_count=summary.k2_win_count,
                long_count=summary.long_count,
                short_count=summary.short_count,
                long_short_ratio=long_short_ratio,
                parse_rate=parse_rate,
                reasoning=reasoning,
            )
            self.history.add_record(record)

            # Persist current prompt
            with open(self.work_dir / "current_prompt.txt", "w", encoding="utf-8") as f:
                f.write(current_prompt)

            # Check if Best
            best = self.history.get_best_record()
            if best and best.generation == gen:
                logger.info(
                    f"🎉 New Best Prompt achieved! K1 Win Rate: {summary.k1_win_rate:.2%}, "
                    f"K2 Win Rate: {summary.k2_win_rate:.2%}"
                )
                if event_callback:
                    event_callback(
                        {
                            "type": "optimizer_log",
                            "message": (
                                f"🎉 New Best Prompt achieved! "
                                f"K1 Win Rate: {summary.k1_win_rate:.2%}, "
                                f"K2 Win Rate: {summary.k2_win_rate:.2%}"
                            ),
                        }
                    )
                best_prompt_path = self.work_dir / f"best_prompt_gen_{gen}.txt"
                with open(best_prompt_path, "w", encoding="utf-8") as f:
                    f.write(current_prompt)
                if event_callback:
                    event_callback(
                        {
                            "type": "optimizer_log",
                            "message": f"Best prompt saved: {best_prompt_path}",
                        }
                    )

            current_run_records.append(
                {
                    "本次运行开始时间": run_started_at,
                    "世代": gen,
                    "记录时间": record.timestamp,
                    "Prompt版本": prompt_version,
                    "Prompt哈希": prompt_hash,
                    "决策模型供应商": self.evaluator_provider,
                    "决策模型": self.evaluator_model,
                    "分析模型供应商": self.analysis_provider,
                    "分析模型": self.analysis_model,
                    "优化模型供应商": self.optimizer_provider,
                    "优化模型": self.optimizer_model,
                    "总样本数": summary.total,
                    "成功数": summary.succeeded,
                    "回测跳过数": summary.backtest_skipped,
                    "失败数": summary.failed,
                    "加载失败数": summary.load_failed,
                    "LLM失败数": summary.llm_failed,
                    "解析失败数": summary.parse_failed,
                    "K1胜率": summary.k1_win_rate,
                    "K1胜利数": summary.k1_win_count,
                    "K2胜率": summary.k2_win_rate,
                    "K2胜利数": summary.k2_win_count,
                    "解析率": parse_rate,
                    "LONG数量": summary.long_count,
                    "SHORT数量": summary.short_count,
                    "HOLD数量": summary.hold_count,
                    "多空比": long_short_ratio,
                    "当时是否最佳": bool(best and best.generation == gen),
                    "导出目录": str(export_dir),
                }
            )

            if cancel_event and cancel_event.is_set():
                logger.info("Batch run cancelled. Aborting evolution after persisting completed generation.")
                if event_callback:
                    event_callback(
                        {
                            "type": "optimizer_log",
                            "message": "Batch run cancelled. Completed generations were persisted; aborting before the next generation.",
                        }
                    )
                break

            # --- Step 2: Generate Next Prompt ---
            if gen == start_generation + max_generations - 1:
                logger.info("Reached maximum generations. Optimization complete.")
                if event_callback:
                    event_callback({"type": "optimizer_log", "message": "Reached maximum generations. Optimization complete."})
                break

            if cancel_event and cancel_event.is_set():
                break

            logger.info("Calling Optimizer LLM to generate the next prompt...")
            if event_callback:
                event_callback({"type": "optimizer_log", "message": "Calling Optimizer LLM to generate the next prompt..."})
                
            meta_prompt = self._generate_meta_prompt(current_prompt)

            try:
                if event_callback:
                    event_callback({"type": "optimizer_stream_status", "stage": "started", "generation": gen + 1})

                chunk_state = {"count": 0}

                def on_chunk(text: str) -> None:
                    chunk_state["count"] += 1
                    if event_callback and chunk_state["count"] == 1:
                        event_callback(
                            {
                                "type": "optimizer_stream_status",
                                "stage": "first_chunk",
                                "generation": gen + 1,
                                "preview": _preview_text(text, 120),
                            }
                        )

                response_text = stream_llm_text(self.llm, meta_prompt, chunk_callback=on_chunk)
                if event_callback:
                    event_callback(
                        {
                            "type": "optimizer_stream_status",
                            "stage": "completed",
                            "generation": gen + 1,
                            "chunks": chunk_state["count"],
                            "chars": len(response_text),
                        }
                    )

                reasoning_output, next_prompt = self._parse_optimizer_response(response_text)

                if not next_prompt:
                    logger.warning("Failed to extract prompt from LLM response. The LLM might have not used <prompt> tags.")
                    logger.warning(f"Raw response snippet: {response_text[:200]}...")
                    logger.warning("Falling back to current prompt for the next generation (which may cause duplicate run).")
                    if event_callback:
                        event_callback(
                            {
                                "type": "optimizer_log",
                                "message": (
                                    "Warning: Failed to extract prompt from LLM response. Falling back to current prompt.\n"
                                    f" - Response Preview: {_preview_text(response_text, 300)}"
                                ),
                            }
                        )
                    next_prompt = current_prompt
                    reasoning = "Fallback: Optimizer failed to provide <prompt> tags."
                else:
                    logger.info("Successfully generated new prompt.")
                    if event_callback:
                        event_callback(
                            {
                                "type": "optimizer_log",
                                "message": (
                                    "Successfully generated new prompt.\n"
                                    f" - Reasoning Preview: {_preview_text(reasoning_output, 300)}\n"
                                    f" - Prompt Length: {len(next_prompt)} chars"
                                ),
                            }
                        )
                        event_callback(
                            {
                                "type": "optimizer_new_prompt",
                                "generation": gen + 1,
                                "prompt": next_prompt,
                                "prompt_chars": len(next_prompt),
                                "reasoning_preview": _preview_text(reasoning_output, 400),
                                "preview": _preview_text(next_prompt),
                            }
                        )
                    current_prompt = next_prompt
                    reasoning = reasoning_output

            except Exception as e:
                logger.error(f"Optimizer LLM invocation failed: {e}")
                logger.error("Stopping evolution loop.")
                if event_callback:
                    event_callback({"type": "optimizer_log", "message": f"Optimizer LLM invocation failed: {e}"})
                    event_callback({"type": "optimizer_failed", "error": str(e)})
                break

        run_summary_csv_path = self._export_run_summary_csv(current_run_records)
        if run_summary_csv_path is not None:
            logger.info(f"Run summary CSV exported: {run_summary_csv_path}")
            if event_callback:
                event_callback(
                    {
                        "type": "optimizer_run_summary_exported",
                        "path": str(run_summary_csv_path),
                        "records": len(current_run_records),
                    }
                )
        else:
            logger.info("No completed generations in this run; skipped run summary CSV export.")
            if event_callback:
                event_callback(
                    {
                        "type": "optimizer_log",
                        "message": "No completed generations in this run; skipped run summary CSV export.",
                    }
                )

        if event_callback:
            event_callback({"type": "optimizer_completed"})


def main():
    parser = argparse.ArgumentParser(description="Auto-Optimizer for Prompt Tuning")
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Path to directory containing historical JSON files for backtesting",
    )
    parser.add_argument(
        "--work-dir",
        type=str,
        default="optimization_logs",
        help="Path to save optimization history and logs (default: optimization_logs)",
    )
    parser.add_argument(
        "--generations",
        type=int,
        default=5,
        help="Number of generations to run (default: 5)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Concurrency for Evaluator LLM backtesting (default: 3)",
    )

    args = parser.parse_args()

    # Ensure config is freshly loaded before creating clients
    reload_config()

    optimizer = AutoOptimizer(data_dir=args.data_dir, work_dir=args.work_dir)
    optimizer.run_evolution_loop(
        max_generations=args.generations, concurrency=args.concurrency
    )


if __name__ == "__main__":
    main()
