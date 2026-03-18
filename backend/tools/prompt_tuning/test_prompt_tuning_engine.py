import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from prompt_tuning_engine import (  # noqa: E402
    BatchBacktestRunner,
    BatchRunConfig,
    ContextLoader,
    DecisionRunner,
)


class FakeResponse:
    def __init__(self, content: str):
        self.content = content


class SequenceLLMFactory:
    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self._lock = threading.Lock()

    def __call__(self, role: str = "agent"):
        del role
        factory = self

        class FakeLLM:
            def invoke(self, prompt: str):
                del prompt
                with factory._lock:
                    if not factory._responses:
                        raise RuntimeError("No fake responses left")
                    return FakeResponse(factory._responses.pop(0))

        return FakeLLM()


class PromptTuningEngineTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.prompt_template = (
            "股票: {stock_name}\n"
            "周期: {time_frame}\n"
            "价格总结: {price_summary}\n"
            "指标: {indicator_report}\n"
            "形态: {pattern_report}\n"
            "趋势: {trend_report}\n"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_history_file(
        self,
        name: str,
        decision_hint: str = "LONG",
        include_future: bool = True,
        nested_reports: bool = False,
    ) -> Path:
        payload = {
            "stock_name": f"BTC-{decision_hint}",
            "time_frame": "4H",
            "price_summary": "summary",
            "price_info_str": "info",
            "latest_price": 100,
            "future_kline_data": (
                [{"close": 110}, {"close": 90}] if include_future else []
            ),
        }
        if nested_reports:
            payload["analysis_results"] = {
                "Indicator": {"indicator_report": "indicator nested"},
                "Pattern": {"pattern_report": "pattern nested"},
                "Trend": {"trend_report": "trend nested"},
            }
        else:
            payload["indicator_report"] = "indicator direct"
            payload["pattern_report"] = "pattern direct"
            payload["trend_report"] = "trend direct"

        file_path = self.temp_path / name
        file_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return file_path

    def test_context_loader_supports_top_level_reports(self):
        file_path = self._write_history_file("direct.json")
        context = ContextLoader().load(file_path)

        self.assertEqual(context.stock_name, "BTC-LONG")
        self.assertEqual(context.indicator_report, "indicator direct")
        self.assertEqual(context.pattern_report, "pattern direct")
        self.assertEqual(context.trend_report, "trend direct")
        self.assertEqual(len(context.future_kline_data), 2)

    def test_context_loader_supports_analysis_results_reports(self):
        file_path = self._write_history_file("nested.json", nested_reports=True)
        context = ContextLoader().load(file_path)

        self.assertEqual(context.indicator_report, "indicator nested")
        self.assertEqual(context.pattern_report, "pattern nested")
        self.assertEqual(context.trend_report, "trend nested")

    def test_decision_runner_parses_fenced_json_and_backtests(self):
        file_path = self._write_history_file("run.json")
        context = ContextLoader().load(file_path)
        runner = DecisionRunner(
            llm_factory=SequenceLLMFactory(['```json\n{"decision":"LONG"}\n```'])
        )

        result = runner.run(context, self.prompt_template, "original")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.decision, "LONG")
        self.assertEqual(result.decision_parse_mode, "fenced_json")
        self.assertEqual(result.k1_result.outcome, "win")
        self.assertEqual(result.k2_result.outcome, "loss")

    def test_decision_runner_handles_direct_json(self):
        file_path = self._write_history_file("direct_run.json")
        context = ContextLoader().load(file_path)
        runner = DecisionRunner(llm_factory=SequenceLLMFactory(['{"decision":"SHORT"}']))

        result = runner.run(context, self.prompt_template, "lite")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.decision, "SHORT")
        self.assertEqual(result.decision_parse_mode, "direct_json")

    def test_decision_runner_marks_parse_failed_for_invalid_output(self):
        file_path = self._write_history_file("parse_failed.json")
        context = ContextLoader().load(file_path)
        runner = DecisionRunner(llm_factory=SequenceLLMFactory(["not json"]))

        result = runner.run(context, self.prompt_template, "lite")

        self.assertEqual(result.status, "parse_failed")
        self.assertIn("JSON", result.error_message)

    def test_decision_runner_marks_backtest_skipped_without_future_data(self):
        file_path = self._write_history_file("skip.json", include_future=False)
        context = ContextLoader().load(file_path)
        runner = DecisionRunner(llm_factory=SequenceLLMFactory(['{"decision":"HOLD"}']))

        result = runner.run(context, self.prompt_template, "lite")

        self.assertEqual(result.status, "backtest_skipped")
        self.assertEqual(result.decision, "HOLD")
        self.assertIn("future_kline_data", result.error_message)

    def test_batch_runner_exports_summary_and_results(self):
        self._write_history_file("a.json")
        self._write_history_file("b.json")
        decision_runner = DecisionRunner(
            llm_factory=SequenceLLMFactory(
                ['{"decision":"LONG"}', '{"decision":"SHORT"}']
            )
        )
        runner = BatchBacktestRunner(decision_runner=decision_runner)
        export_dir = self.temp_path / "exports"
        events = []

        summary, results = runner.run(
            BatchRunConfig(
                input_dir=str(self.temp_path),
                prompt_template=self.prompt_template,
                prompt_version="original",
                export_dir=str(export_dir),
                concurrency=2,
            ),
            event_callback=events.append,
        )

        self.assertEqual(summary.total, 2)
        self.assertEqual(len(results), 2)
        self.assertTrue((export_dir / "batch_results.json").exists())
        self.assertTrue((export_dir / "batch_results.csv").exists())

        payload = json.loads(
            (export_dir / "batch_results.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["run_config"]["prompt_version"], "original")
        self.assertIn("prompt_sha256", payload["run_config"])
        self.assertEqual(len(payload["results"]), 2)
        self.assertNotIn("raw_response", payload["results"][0])
        self.assertNotIn("formatted_prompt", payload["results"][0])
        self.assertTrue(any(event["type"] == "batch_started" for event in events))
        self.assertTrue(any(event["type"] == "batch_completed" for event in events))

    def test_batch_runner_keeps_running_when_one_file_is_invalid(self):
        self._write_history_file("good.json")
        (self.temp_path / "bad.json").write_text("{bad json", encoding="utf-8")
        decision_runner = DecisionRunner(
            llm_factory=SequenceLLMFactory(['{"decision":"LONG"}'])
        )
        runner = BatchBacktestRunner(decision_runner=decision_runner)
        export_dir = self.temp_path / "exports_invalid"

        summary, results = runner.run(
            BatchRunConfig(
                input_dir=str(self.temp_path),
                prompt_template=self.prompt_template,
                prompt_version="lite",
                export_dir=str(export_dir),
                concurrency=2,
            )
        )

        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.load_failed, 1)
        self.assertEqual(summary.succeeded, 1)
        self.assertEqual(len(results), 2)
        self.assertTrue(any(result.status == "load_failed" for result in results))

    def test_decision_runner_supports_unescaped_json_in_prompt_template(self):
        file_path = self._write_history_file("json_prompt.json")
        context = ContextLoader().load(file_path)
        runner = DecisionRunner(llm_factory=SequenceLLMFactory(['{"decision":"LONG"}']))
        prompt_template = (
            '请分析 {stock_name} {time_frame}\n'
            '{\n'
            '  "forecast_horizon": "next N candles",\n'
            '  "decision": "LONG | SHORT | HOLD",\n'
            '  "indicator": "{indicator_report}"\n'
            '}\n'
        )

        result = runner.run(context, prompt_template, "optimized")

        self.assertEqual(result.status, "success")
        self.assertIn('"forecast_horizon": "next N candles"', result.formatted_prompt)
        self.assertIn('"indicator": "indicator direct"', result.formatted_prompt)

    def test_batch_runner_stops_submitting_new_tasks_after_cancel(self):
        for index in range(5):
            self._write_history_file(f"{index}.json")

        decision_runner = DecisionRunner(
            llm_factory=SequenceLLMFactory(['{"decision":"LONG"}'] * 5)
        )
        runner = BatchBacktestRunner(decision_runner=decision_runner)
        export_dir = self.temp_path / "exports_cancel"
        cancel_event = threading.Event()
        observed_start = 0

        def capture_and_cancel(event):
            nonlocal observed_start
            if event["type"] == "file_started":
                observed_start += 1
                if observed_start == 1:
                    cancel_event.set()

        summary, results = runner.run(
            BatchRunConfig(
                input_dir=str(self.temp_path),
                prompt_template=self.prompt_template,
                prompt_version="original",
                export_dir=str(export_dir),
                concurrency=1,
            ),
            cancel_event=cancel_event,
            event_callback=capture_and_cancel,
        )

        self.assertLess(summary.total, 5)
        self.assertEqual(len(results), summary.total)


if __name__ == "__main__":
    unittest.main()
