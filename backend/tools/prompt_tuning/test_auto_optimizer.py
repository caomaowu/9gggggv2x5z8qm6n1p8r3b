import csv
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch


CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent.parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from auto_optimizer import AutoOptimizer  # noqa: E402
from prompt_tuning_engine import BatchRunSummary  # noqa: E402


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeOptimizerLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def stream(self, payload):
        self.calls.append(payload)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        for item in response:
            if isinstance(item, Exception):
                raise item
            yield item


class FakeBatchRunner:
    def __init__(self, summary: BatchRunSummary):
        self.summary = summary
        self.calls = []

    def run(self, config, cancel_event=None, event_callback=None):
        del cancel_event, event_callback
        self.calls.append(config)
        return self.summary, []


class CancelAfterFirstBatchRunner(FakeBatchRunner):
    def run(self, config, cancel_event=None, event_callback=None):
        if cancel_event is not None:
            cancel_event.set()
        return super().run(config, cancel_event=cancel_event, event_callback=event_callback)


class AutoOptimizerTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.summary = BatchRunSummary(
            total=5,
            succeeded=5,
            backtest_skipped=0,
            long_count=3,
            short_count=2,
            hold_count=0,
            k1_win_rate=0.4,
            k1_win_count=2,
            k2_win_rate=0.8,
            k2_win_count=4,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_optimizer(self, llm):
        with patch("auto_optimizer.create_optimizer_llm", return_value=llm):
            optimizer = AutoOptimizer(
                data_dir=str(self.temp_path),
                work_dir=str(self.temp_path / "work"),
            )
        optimizer.runner = FakeBatchRunner(self.summary)
        return optimizer

    def test_optimizer_retries_after_model_dump_error(self):
        llm = FakeOptimizerLLM(
            [
                AttributeError("'str' object has no attribute 'model_dump'"),
                [FakeResponse("analysis\n"), FakeResponse("<prompt>improved prompt</prompt>")],
            ]
        )
        optimizer = self._create_optimizer(llm)
        events = []

        optimizer.run_evolution_loop(max_generations=2, concurrency=1, event_callback=events.append)

        self.assertEqual(len(optimizer.history.records), 2)
        self.assertEqual(optimizer.history.records[1].prompt_content, "improved prompt")
        self.assertTrue(
            any(event.get("type") == "optimizer_run_summary_exported" for event in events)
        )
        self.assertTrue(
            any(
                event.get("type") == "optimizer_new_prompt"
                and event.get("prompt") == "improved prompt"
                for event in events
            )
        )
        self.assertEqual(optimizer.history.records[0].k1_win_rate, 0.4)
        self.assertEqual(optimizer.history.records[0].k2_win_rate, 0.8)
        self.assertEqual(llm.calls[0], unittest.mock.ANY)
        self.assertEqual(llm.calls[1], [("human", llm.calls[0])])
        self.assertTrue(any(event.get("type") == "optimizer_stream_status" for event in events))

    def test_optimizer_falls_back_when_prompt_tags_missing(self):
        llm = FakeOptimizerLLM([[FakeResponse("analysis without prompt tags")]])
        optimizer = self._create_optimizer(llm)
        events = []

        optimizer.run_evolution_loop(max_generations=2, concurrency=1, event_callback=events.append)

        self.assertEqual(len(optimizer.history.records), 2)
        self.assertEqual(
            optimizer.history.records[1].reasoning,
            "Fallback: Optimizer failed to provide <prompt> tags.",
        )
        self.assertNotIn(
            {"type": "optimizer_new_prompt", "prompt": "improved prompt"},
            events,
        )

    def test_run_summary_csv_exports_only_current_run_with_model_info(self):
        work_dir = self.temp_path / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        history_file = work_dir / "optimization_history.json"
        old_record = {
            "generation": 7,
            "timestamp": "2026-03-18T11:40:00+08:00",
            "prompt_content": "old prompt",
            "prompt_hash": "oldhash1",
            "total_trades": 3,
            "win_rate": 0.33,
            "k1_win_rate": 0.33,
            "k1_win_count": 1,
            "k2_win_rate": 0.66,
            "k2_win_count": 2,
            "long_count": 1,
            "short_count": 2,
            "long_short_ratio": 0.5,
            "parse_rate": 1.0,
            "reasoning": "old",
        }
        history_file.write_text(json.dumps([old_record], ensure_ascii=False), encoding="utf-8")

        llm = FakeOptimizerLLM([])
        optimizer = self._create_optimizer(llm)
        events = []

        optimizer.run_evolution_loop(max_generations=1, concurrency=1, event_callback=events.append)

        export_event = next(
            event for event in events if event.get("type") == "optimizer_run_summary_exported"
        )
        csv_path = Path(export_event["path"])
        self.assertTrue(csv_path.exists())

        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["世代"], "8")
        self.assertEqual(rows[0]["决策模型供应商"], optimizer.evaluator_provider)
        self.assertEqual(rows[0]["决策模型"], optimizer.evaluator_model)
        self.assertEqual(rows[0]["分析模型供应商"], optimizer.analysis_provider)
        self.assertEqual(rows[0]["分析模型"], optimizer.analysis_model)
        self.assertEqual(rows[0]["优化模型供应商"], optimizer.optimizer_provider)
        self.assertEqual(rows[0]["优化模型"], optimizer.optimizer_model)
        self.assertEqual(rows[0]["K1胜率"], "0.4")
        self.assertEqual(rows[0]["K2胜率"], "0.8")

    def test_run_summary_csv_exports_completed_generations_when_cancelled(self):
        llm = FakeOptimizerLLM([])
        optimizer = self._create_optimizer(llm)
        optimizer.runner = CancelAfterFirstBatchRunner(self.summary)
        events = []
        cancel_event = threading.Event()

        optimizer.run_evolution_loop(
            max_generations=3,
            concurrency=1,
            cancel_event=cancel_event,
            event_callback=events.append,
        )

        export_event = next(
            event for event in events if event.get("type") == "optimizer_run_summary_exported"
        )
        csv_path = Path(export_event["path"])
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["世代"], "1")
        self.assertTrue(cancel_event.is_set())

    def test_run_summary_csv_is_skipped_when_no_generation_completes(self):
        llm = FakeOptimizerLLM([])
        optimizer = self._create_optimizer(llm)
        events = []
        cancel_event = threading.Event()
        cancel_event.set()

        optimizer.run_evolution_loop(
            max_generations=2,
            concurrency=1,
            cancel_event=cancel_event,
            event_callback=events.append,
        )

        self.assertFalse(
            any(event.get("type") == "optimizer_run_summary_exported" for event in events)
        )
        self.assertEqual(
            list((self.temp_path / "work").glob("optimization_run_summary_*.csv")),
            [],
        )


if __name__ == "__main__":
    unittest.main()
