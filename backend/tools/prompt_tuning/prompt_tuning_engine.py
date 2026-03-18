from __future__ import annotations

import csv
import hashlib
import json
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional


backend_dir = Path(__file__).resolve().parent.parent.parent

try:
    from app.core.config import create_llm_client
    from app.utils.llm_compat import invoke_llm_text
    from app.utils.prompt_template import render_prompt_template
except ImportError:
    create_llm_client = None
    invoke_llm_text = None
    render_prompt_template = None


VALID_DECISIONS = {"LONG", "SHORT", "HOLD"}
CSV_FIELDNAMES = [
    "文件名",
    "代币名称",
    "时间周期",
    "Prompt版本",
    "状态",
    "决策",
    "最新价格",
    "K1收盘价",
    "K1涨跌幅",
    "K1结果",
    "K2收盘价",
    "K2涨跌幅",
    "K2结果",
    "耗时(ms)",
    "错误信息",
]


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def safe_float(value: Any) -> Optional[float]:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class PromptTuningContext:
    source_file: str
    stock_name: str
    time_frame: str
    price_summary: str
    price_info_str: str
    latest_price_str: str
    latest_price: Optional[float]
    future_kline_data: list[dict[str, Any]]
    indicator_report: str
    pattern_report: str
    trend_report: str

    def to_preview_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "stock_name": self.stock_name,
            "time_frame": self.time_frame,
            "price_summary": self.price_summary,
            "price_info_str": self.price_info_str,
            "latest_price_str": self.latest_price_str,
            "latest_price": self.latest_price,
            "future_kline_count": len(self.future_kline_data),
            "indicator_report": self.indicator_report,
            "pattern_report": self.pattern_report,
            "trend_report": self.trend_report,
        }


@dataclass
class BacktestPointResult:
    close: Optional[float] = None
    pct: Optional[float] = None
    outcome: str = "missing"


@dataclass
class PromptRunResult:
    source_file: str
    file_name: str
    stock_name: str
    time_frame: str
    latest_price: Optional[float]
    status: str
    decision: str
    decision_parse_mode: str
    has_future_kline_data: bool
    prompt_version: str = ""
    k1_result: BacktestPointResult = field(default_factory=BacktestPointResult)
    k2_result: BacktestPointResult = field(default_factory=BacktestPointResult)
    elapsed_ms: int = 0
    error_message: str = ""
    started_at: str = ""
    finished_at: str = ""
    formatted_prompt: str = ""
    raw_response: str = ""

    def to_export_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("formatted_prompt", None)
        data.pop("raw_response", None)
        return data

    def to_csv_row(self) -> dict[str, Any]:
        return {
            "文件名": self.file_name,
            "代币名称": self.stock_name,
            "时间周期": self.time_frame,
            "Prompt版本": self.prompt_version,
            "状态": self.status,
            "决策": self.decision,
            "最新价格": self.latest_price,
            "K1收盘价": self.k1_result.close,
            "K1涨跌幅": self.k1_result.pct,
            "K1结果": self.k1_result.outcome,
            "K2收盘价": self.k2_result.close,
            "K2涨跌幅": self.k2_result.pct,
            "K2结果": self.k2_result.outcome,
            "耗时(ms)": self.elapsed_ms,
            "错误信息": self.error_message,
        }


@dataclass
class BatchRunConfig:
    input_dir: str
    prompt_template: str
    prompt_version: str
    export_dir: str
    concurrency: int = 3


@dataclass
class BatchRunSummary:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    load_failed: int = 0
    llm_failed: int = 0
    parse_failed: int = 0
    backtest_skipped: int = 0
    long_count: int = 0
    short_count: int = 0
    hold_count: int = 0
    k1_win_count: int = 0
    k2_win_count: int = 0
    k1_win_rate: float = 0.0
    k2_win_rate: float = 0.0
    avg_elapsed_ms: float = 0.0
    export_json_path: str = ""
    export_csv_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContextLoader:
    def load(self, file_path: str | Path) -> PromptTuningContext:
        path = Path(file_path)
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        indicator_report = data.get("indicator_report", "")
        pattern_report = data.get("pattern_report", "")
        trend_report = data.get("trend_report", "")

        analysis_results = data.get("analysis_results", {})
        if isinstance(analysis_results, dict):
            indicator_report = (
                analysis_results.get("Indicator", {}).get("indicator_report")
                or indicator_report
            )
            pattern_report = (
                analysis_results.get("Pattern", {}).get("pattern_report")
                or pattern_report
            )
            trend_report = (
                analysis_results.get("Trend", {}).get("trend_report") or trend_report
            )

        latest_price_value = data.get("latest_price", "Unknown")
        latest_price = safe_float(latest_price_value)

        future_kline_data = data.get("future_kline_data", [])
        if not isinstance(future_kline_data, list):
            future_kline_data = []

        return PromptTuningContext(
            source_file=str(path.resolve()),
            stock_name=data.get("stock_name", "Unknown"),
            time_frame=data.get("time_frame", "Unknown"),
            price_summary=data.get("price_summary", "No price summary available."),
            price_info_str=data.get("price_info_str", "No price info available."),
            latest_price_str=str(latest_price_value),
            latest_price=latest_price,
            future_kline_data=future_kline_data,
            indicator_report=indicator_report,
            pattern_report=pattern_report,
            trend_report=trend_report,
        )


class DecisionRunner:
    def __init__(self, llm_factory: Optional[Callable[..., Any]] = None):
        self.llm_factory = llm_factory or create_llm_client

    def run(
        self,
        context: PromptTuningContext,
        template: str,
        prompt_version: str,
    ) -> PromptRunResult:
        started_at = now_iso()
        start_time = time.perf_counter()
        result = PromptRunResult(
            source_file=context.source_file,
            file_name=Path(context.source_file).name,
            stock_name=context.stock_name,
            time_frame=context.time_frame,
            latest_price=context.latest_price,
            status="llm_failed",
            decision="",
            decision_parse_mode="none",
            has_future_kline_data=bool(context.future_kline_data),
            prompt_version=prompt_version,
            started_at=started_at,
        )

        try:
            if render_prompt_template is None:
                raise RuntimeError("Prompt template helper is not available.")
            prompt = render_prompt_template(
                template,
                stock_name=context.stock_name,
                time_frame=context.time_frame,
                price_summary=context.price_summary,
                price_info_str=context.price_info_str,
                latest_price_str=context.latest_price_str,
                indicator_report=context.indicator_report,
                pattern_report=context.pattern_report,
                trend_report=context.trend_report,
            )
            result.formatted_prompt = prompt
        except Exception as exc:
            result.status = "parse_failed"
            result.error_message = f"Prompt 格式化失败: {exc}"
            return self._finalize_result(result, start_time)

        try:
            if self.llm_factory is None:
                raise RuntimeError("LLM client factory is not available.")
            if invoke_llm_text is None:
                raise RuntimeError("LLM compatibility helper is not available.")
            llm = self.llm_factory(role="agent")
            result.raw_response = invoke_llm_text(llm, prompt)
        except Exception as exc:
            result.status = "llm_failed"
            result.error_message = str(exc)
            return self._finalize_result(result, start_time)

        try:
            decision_json, parse_mode = self._parse_decision_output(result.raw_response)
            action = str(decision_json.get("decision", "")).upper().strip()
            if action not in VALID_DECISIONS:
                raise ValueError("未解析到有效 decision 字段")
            result.decision = action
            result.decision_parse_mode = parse_mode
        except Exception as exc:
            result.status = "parse_failed"
            result.error_message = str(exc)
            return self._finalize_result(result, start_time)

        self._evaluate_backtest(result, context)
        return self._finalize_result(result, start_time)

    def _finalize_result(
        self,
        result: PromptRunResult,
        start_time: float,
    ) -> PromptRunResult:
        result.finished_at = now_iso()
        result.elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return result

    def _parse_decision_output(
        self,
        raw_response: str,
    ) -> tuple[dict[str, Any], str]:
        if not raw_response.strip():
            raise ValueError("LLM 返回为空")

        fenced_matches = re.finditer(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            raw_response,
            re.IGNORECASE | re.DOTALL,
        )
        for match in fenced_matches:
            payload = match.group(1)
            try:
                return json.loads(payload), "fenced_json"
            except json.JSONDecodeError:
                continue

        stripped = raw_response.strip()
        try:
            return json.loads(stripped), "direct_json"
        except json.JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        brace_index = stripped.find("{")
        if brace_index >= 0:
            payload, _ = decoder.raw_decode(stripped[brace_index:])
            if isinstance(payload, dict):
                return payload, "embedded_json"

        raise ValueError("无法解析 LLM 输出中的 JSON")

    def _evaluate_backtest(
        self,
        result: PromptRunResult,
        context: PromptTuningContext,
    ) -> None:
        latest_price = context.latest_price
        if latest_price is None or latest_price <= 0:
            result.status = "backtest_skipped"
            result.error_message = "缺少可用的 latest_price，无法回测"
            return

        future_data = context.future_kline_data
        if not future_data:
            result.status = "backtest_skipped"
            result.error_message = "缺少 future_kline_data，无法回测"
            return

        result.k1_result = self._evaluate_point(result.decision, latest_price, future_data, 0)
        result.k2_result = self._evaluate_point(result.decision, latest_price, future_data, 1)
        result.status = "success"

    def _evaluate_point(
        self,
        decision: str,
        latest_price: float,
        future_data: list[dict[str, Any]],
        index: int,
    ) -> BacktestPointResult:
        if index >= len(future_data):
            return BacktestPointResult()

        point = future_data[index] or {}
        close_value = safe_float(point.get("close"))
        if close_value is None:
            return BacktestPointResult()

        pct = ((close_value - latest_price) / latest_price) * 100
        if decision == "HOLD":
            outcome = "hold"
        elif decision == "LONG":
            outcome = "win" if close_value > latest_price else "loss"
        else:
            outcome = "win" if close_value < latest_price else "loss"

        return BacktestPointResult(close=close_value, pct=round(pct, 6), outcome=outcome)


class BatchBacktestRunner:
    def __init__(
        self,
        context_loader: Optional[ContextLoader] = None,
        decision_runner: Optional[DecisionRunner] = None,
    ):
        self.context_loader = context_loader or ContextLoader()
        self.decision_runner = decision_runner or DecisionRunner()

    def run(
        self,
        config: BatchRunConfig,
        cancel_event: Optional[threading.Event] = None,
        event_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> tuple[BatchRunSummary, list[PromptRunResult]]:
        input_dir = Path(config.input_dir)
        export_dir = Path(config.export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        all_files = sorted(path for path in input_dir.glob("*.json") if path.is_file())
        total_files = len(all_files)
        started_at = now_iso()
        prompt_sha256 = hashlib.sha256(
            config.prompt_template.encode("utf-8")
        ).hexdigest()

        self._emit_event(
            event_callback,
            {
                "type": "batch_started",
                "total_files": total_files,
                "input_dir": str(input_dir.resolve()),
                "export_dir": str(export_dir.resolve()),
            },
        )

        if total_files == 0:
            summary = BatchRunSummary()
            json_path, csv_path = self._export_results(
                export_dir=export_dir,
                run_config={
                    "input_dir": str(input_dir.resolve()),
                    "prompt_version": config.prompt_version,
                    "prompt_sha256": prompt_sha256,
                    "concurrency": self._normalize_concurrency(config.concurrency),
                    "started_at": started_at,
                    "finished_at": now_iso(),
                    "total_files": total_files,
                    "cancelled": False,
                },
                summary=summary,
                results=[],
            )
            summary.export_json_path = str(json_path)
            summary.export_csv_path = str(csv_path)
            self._emit_event(
                event_callback,
                {
                    "type": "batch_completed",
                    "summary": summary.to_dict(),
                    "results": [],
                    "cancelled": False,
                },
            )
            return summary, []

        max_workers = self._normalize_concurrency(config.concurrency)
        results_by_index: list[tuple[int, PromptRunResult]] = []
        submitted_count = 0
        futures: dict[Future[PromptRunResult], tuple[int, Path]] = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            next_index = 0
            while next_index < total_files and len(futures) < max_workers:
                if cancel_event and cancel_event.is_set():
                    break
                future = executor.submit(
                    self._run_single_file,
                    all_files[next_index],
                    config.prompt_template,
                    config.prompt_version,
                    event_callback,
                )
                futures[future] = (next_index, all_files[next_index])
                submitted_count += 1
                next_index += 1

            while futures:
                done, _ = wait(futures.keys(), return_when=FIRST_COMPLETED)
                for future in done:
                    index, path = futures.pop(future)
                    result = future.result()
                    results_by_index.append((index, result))
                    self._emit_event(
                        event_callback,
                        {
                            "type": "file_completed",
                            "result": result.to_export_dict(),
                            "processed_count": len(results_by_index),
                            "submitted_count": submitted_count,
                            "file_name": path.name,
                        },
                    )

                    while next_index < total_files and len(futures) < max_workers:
                        if cancel_event and cancel_event.is_set():
                            break
                        future = executor.submit(
                            self._run_single_file,
                            all_files[next_index],
                            config.prompt_template,
                            config.prompt_version,
                            event_callback,
                        )
                        futures[future] = (next_index, all_files[next_index])
                        submitted_count += 1
                        next_index += 1

        results_by_index.sort(key=lambda item: item[0])
        results = [item[1] for item in results_by_index]
        summary = self._build_summary(results)
        cancelled = bool(cancel_event and cancel_event.is_set())
        finished_at = now_iso()

        json_path, csv_path = self._export_results(
            export_dir=export_dir,
            run_config={
                "input_dir": str(input_dir.resolve()),
                "prompt_version": config.prompt_version,
                "prompt_sha256": prompt_sha256,
                "concurrency": max_workers,
                "started_at": started_at,
                "finished_at": finished_at,
                "total_files": total_files,
                "submitted_files": submitted_count,
                "cancelled": cancelled,
            },
            summary=summary,
            results=results,
        )
        summary.export_json_path = str(json_path)
        summary.export_csv_path = str(csv_path)

        self._emit_event(
            event_callback,
            {
                "type": "batch_completed",
                "summary": summary.to_dict(),
                "results": [result.to_export_dict() for result in results],
                "cancelled": cancelled,
            },
        )
        return summary, results

    def _run_single_file(
        self,
        file_path: Path,
        prompt_template: str,
        prompt_version: str,
        event_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> PromptRunResult:
        self._emit_event(
            event_callback,
            {
                "type": "file_started",
                "file_name": file_path.name,
                "source_file": str(file_path.resolve()),
            },
        )

        try:
            context = self.context_loader.load(file_path)
        except Exception as exc:
            timestamp = now_iso()
            return PromptRunResult(
                source_file=str(file_path.resolve()),
                file_name=file_path.name,
                stock_name="Unknown",
                time_frame="Unknown",
                latest_price=None,
                status="load_failed",
                decision="",
                decision_parse_mode="none",
                has_future_kline_data=False,
                error_message=str(exc),
                started_at=timestamp,
                finished_at=timestamp,
            )

        return self.decision_runner.run(context, prompt_template, prompt_version)

    def _build_summary(self, results: list[PromptRunResult]) -> BatchRunSummary:
        summary = BatchRunSummary(total=len(results))
        k1_eligible = 0
        k2_eligible = 0

        for result in results:
            if result.status == "success":
                summary.succeeded += 1
            elif result.status == "load_failed":
                summary.load_failed += 1
            elif result.status == "llm_failed":
                summary.llm_failed += 1
            elif result.status == "parse_failed":
                summary.parse_failed += 1
            elif result.status == "backtest_skipped":
                summary.backtest_skipped += 1

            if result.decision == "LONG":
                summary.long_count += 1
            elif result.decision == "SHORT":
                summary.short_count += 1
            elif result.decision == "HOLD":
                summary.hold_count += 1

            if result.k1_result.outcome in {"win", "loss"}:
                k1_eligible += 1
            if result.k1_result.outcome == "win":
                summary.k1_win_count += 1

            if result.k2_result.outcome in {"win", "loss"}:
                k2_eligible += 1
            if result.k2_result.outcome == "win":
                summary.k2_win_count += 1

        summary.failed = (
            summary.load_failed + summary.llm_failed + summary.parse_failed
        )
        summary.k1_win_rate = round(
            summary.k1_win_count / k1_eligible, 6
        ) if k1_eligible else 0.0
        summary.k2_win_rate = round(
            summary.k2_win_count / k2_eligible, 6
        ) if k2_eligible else 0.0
        summary.avg_elapsed_ms = round(
            sum(result.elapsed_ms for result in results) / len(results), 2
        ) if results else 0.0
        return summary

    def _export_results(
        self,
        export_dir: Path,
        run_config: dict[str, Any],
        summary: BatchRunSummary,
        results: list[PromptRunResult],
    ) -> tuple[Path, Path]:
        json_path = export_dir / "batch_results.json"
        csv_path = export_dir / "batch_results.csv"

        payload = {
            "run_config": run_config,
            "summary": summary.to_dict(),
            "results": [result.to_export_dict() for result in results],
        }
        with json_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

        with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDNAMES)
            writer.writeheader()
            for result in results:
                writer.writerow(result.to_csv_row())

            # Append summary statistics
            file.write("\n")
            summary_writer = csv.writer(file)
            summary_writer.writerow(["", "", "统计摘要"])
            summary_writer.writerow(["", "", "K1胜率", f"{summary.k1_win_rate:.2%}", "K1获胜数", summary.k1_win_count])
            summary_writer.writerow(["", "", "K2胜率", f"{summary.k2_win_rate:.2%}", "K2获胜数", summary.k2_win_count])
            summary_writer.writerow(["", "", "总样本数", summary.total, "成功回测", summary.succeeded])

        return json_path, csv_path

    def _normalize_concurrency(self, concurrency: int) -> int:
        return max(1, min(20, int(concurrency)))

    def _emit_event(
        self,
        event_callback: Optional[Callable[[dict[str, Any]], None]],
        event: dict[str, Any],
    ) -> None:
        if event_callback is None:
            return
        try:
            event_callback(event)
        except Exception:
            return
