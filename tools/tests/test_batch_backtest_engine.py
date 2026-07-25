import csv
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


TOOLS_DIR = Path(__file__).resolve().parents[1]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from batch_backtest_app import core, engine  # noqa: E402


DEFAULTS = {
    "asset": "",
    "timeframe": "1h",
    "end_date": "",
    "end_time": "",
    "kline_count": 40,
    "future_kline_count": 13,
    "ai_version": "original",
    "data_method": "to_end",
}


def test_csv_writer_concurrent_writes_are_complete(tmp_path):
    output = tmp_path / "results.csv"
    fieldnames = ["task_id", "value"]
    engine.ensure_output_header(str(output), fieldnames)

    writer = engine.CsvWriter(str(output), fieldnames)
    writer.start()
    with ThreadPoolExecutor(max_workers=64) as pool:
        futures = [pool.submit(writer.write, {"task_id": str(i), "value": i}) for i in range(2000)]
        for future in futures:
            future.result()
    writer.stop()

    with output.open("r", encoding="utf-8", newline="") as file_obj:
        rows = list(csv.DictReader(file_obj))
    assert len(rows) == 2000
    assert {row["task_id"] for row in rows} == {str(i) for i in range(2000)}
    assert writer.rows_written == 2000


def test_extreme_requested_concurrency_is_bounded_without_dropping(monkeypatch):
    active = 0
    peak_active = 0
    lock = threading.Lock()

    def fake_run_one_task(*args):
        nonlocal active, peak_active
        row = args[-2]
        with lock:
            active += 1
            peak_active = max(peak_active, active)
        time.sleep(0.005)
        with lock:
            active -= 1
        return {"task_id": row["task_id"]}

    monkeypatch.setattr(engine, "MAX_SAFE_WORKERS", 4)
    monkeypatch.setattr(engine, "run_one_task", fake_run_one_task)
    rows = [{"task_id": str(i)} for i in range(80)]

    results = list(
        engine.run_tasks_concurrently(
            "http://localhost",
            "/analyze",
            1.0,
            0,
            0.0,
            0.0,
            rows,
            DEFAULTS,
            max_workers=1000,
        )
    )

    assert len(results) == len(rows)
    assert {item["task_id"] for item in results} == {row["task_id"] for row in rows}
    assert peak_active <= 4


def test_worker_exception_becomes_error_result(monkeypatch):
    def fake_run_one_task(*args):
        row = args[-2]
        if row["task_id"] == "bad":
            raise RuntimeError("worker exploded")
        return {"task_id": row["task_id"], "error": ""}

    monkeypatch.setattr(engine, "run_one_task", fake_run_one_task)
    rows = [{"task_id": "ok"}, {"task_id": "bad"}]
    results = list(
        engine.run_tasks_concurrently(
            "http://localhost",
            "/analyze",
            1.0,
            0,
            0.0,
            0.0,
            rows,
            DEFAULTS,
            max_workers=1000,
        )
    )

    by_id = {item["task_id"]: item for item in results}
    assert len(by_id) == 2
    assert by_id["bad"]["is_correct"] == "Error"
    assert "worker exploded" in by_id["bad"]["error"]


def test_k1_k2_are_scored_independently_with_confidence_gate(monkeypatch):
    def fake_post(**_kwargs):
        return {
            "result_id": "R-test",
            "latest_price": 100.0,
            "decision": {
                "k1_action": "LONG",
                "k1_confidence": 0.82,
                "k2_action": "SHORT",
                "k2_confidence": 0.65,
            },
            "future_kline_data": [{"close": 101.0}, {"close": 99.0}],
        }

    monkeypatch.setattr(engine, "_post_with_retry", fake_post)
    row = {
        "task_id": "dual",
        "asset": "ETH",
        "timeframe": "4h+15m",
        "end_date": "2026-01-01",
        "end_time": "15:55",
    }
    result = engine.run_one_task(
        "http://localhost", "/analyze", 1.0, 0, 0.0, 0.70, row, DEFAULTS
    )

    assert result["ai_decision_k1"] == "LONG"
    assert result["is_correct_1"] == "True"
    assert result["ai_decision_k2"] == "HOLD"
    assert result["is_correct_2"] == "Hold"


def test_summary_reports_selective_coverage():
    summary = core.compute_summary_from_rows(
        [
            {"ai_decision_k1": "LONG", "is_correct_1": "True", "ai_decision_k2": "SHORT", "is_correct_2": "False"},
            {"ai_decision_k1": "HOLD", "is_correct_1": "Hold", "ai_decision_k2": "LONG", "is_correct_2": "True"},
            {"ai_decision_k1": "HOLD", "is_correct_1": "Hold", "ai_decision_k2": "HOLD", "is_correct_2": "Hold"},
        ]
    )

    assert summary["win_rate_1"] == 100.0
    assert summary["coverage_1"] == pytest.approx(100.0 / 3.0)
    assert summary["win_rate_2"] == 50.0
    assert summary["coverage_2"] == pytest.approx(200.0 / 3.0)
