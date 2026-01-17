import argparse
import csv
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


REQUIRED_TASK_FIELDS = {"task_id", "asset", "timeframe", "end_date", "end_time"}


@dataclass(frozen=True)
class TaskKey:
    asset: str
    timeframe: str
    end_date: str
    end_time: str
    data_method: str
    ai_version: str
    kline_count: int
    future_kline_count: int


def _normalize_base_url(base_url: str) -> str:
    base_url = base_url.strip()
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    return base_url


def _task_key_from_row(row: Dict[str, str], defaults: Dict[str, Any]) -> TaskKey:
    def get_str(name: str, default_value: str) -> str:
        value = (row.get(name) or "").strip()
        return value if value else str(default_value)

    def get_int(name: str, default_value: int) -> int:
        raw = (row.get(name) or "").strip()
        if not raw:
            return int(default_value)
        return int(float(raw))

    return TaskKey(
        asset=get_str("asset", defaults["asset"]),
        timeframe=get_str("timeframe", defaults["timeframe"]),
        end_date=get_str("end_date", defaults["end_date"]),
        end_time=get_str("end_time", defaults["end_time"]),
        data_method=get_str("data_method", defaults["data_method"]),
        ai_version=get_str("ai_version", defaults["ai_version"]),
        kline_count=get_int("kline_count", defaults["kline_count"]),
        future_kline_count=get_int("future_kline_count", defaults["future_kline_count"]),
    )


def _try_parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("%", "").strip()
    try:
        return float(text)
    except Exception:
        return None


def _extract_close(item: Dict[str, Any]) -> Optional[float]:
    for key in ("close", "Close", "c", "CLOSE"):
        if key in item:
            parsed = _try_parse_float(item.get(key))
            if parsed is not None:
                return parsed
    return None


def _normalize_action(action: Any) -> str:
    if action is None:
        return "HOLD"
    text = str(action).strip().upper()
    if text in {"BUY", "LONG"}:
        return "LONG"
    if text in {"SELL", "SHORT"}:
        return "SHORT"
    if text in {"HOLD", "WAIT", "NEUTRAL"}:
        return "HOLD"
    return text or "HOLD"


def _compute_is_correct(action: str, actual_change: Optional[float], hold_threshold: float) -> str:
    if actual_change is None:
        return "NoFutureData"
    if action == "LONG":
        return "True" if actual_change > 0 else "False"
    if action == "SHORT":
        return "True" if actual_change < 0 else "False"
    if action == "HOLD":
        return "True" if abs(actual_change) <= hold_threshold else "False"
    return "Unknown"


def _judge_prediction_two_kline(
    action: str,
    analysis_price: Optional[float],
    future_close_1: Optional[float],
    future_close_2: Optional[float],
) -> str:
    action = _normalize_action(action)

    if analysis_price is None or analysis_price == 0:
        return "NoBaselinePrice"

    if future_close_1 is None or future_close_2 is None:
        return "NoFutureData"

    if action not in {"LONG", "SHORT"}:
        return "Unknown"

    if action == "LONG":
        match_1 = future_close_1 > analysis_price
        match_2 = future_close_2 > analysis_price
        no_loss = future_close_2 >= analysis_price
    else:
        match_1 = future_close_1 < analysis_price
        match_2 = future_close_2 < analysis_price
        no_loss = future_close_2 <= analysis_price

    if match_1 and match_2:
        return "True"
    if (not match_1) and match_2 and no_loss:
        return "True"
    if match_1 and (not match_2) and no_loss:
        return "True"
    return "False"



def _load_existing_keys(output_csv: str) -> Tuple[Optional[List[str]], set]:
    if not os.path.exists(output_csv):
        return None, set()
    
    with open(output_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        keys = set()
        for row in reader:
            try:
                key = TaskKey(
                    asset=(row.get("asset") or "").strip(),
                    timeframe=(row.get("timeframe") or "").strip(),
                    end_date=(row.get("end_date") or row.get("date") or "").strip().split(" ")[0],
                    end_time=(row.get("end_time") or "").strip(),
                    data_method=(row.get("data_method") or row.get("data_method_short") or "to_end").strip(),
                    ai_version=(row.get("ai_version") or row.get("agent_version") or "original").strip(),
                    kline_count=int(float((row.get("kline_count") or "100").strip() or 100)),
                    future_kline_count=int(float((row.get("future_kline_count") or "13").strip() or 13)),
                )
                keys.add(key)
            except Exception:
                continue
        return header, keys


def _migrate_output_csv_in_place(output_csv: str, fieldnames: List[str]) -> None:
    if not os.path.exists(output_csv) or os.path.getsize(output_csv) == 0:
        _ensure_output_header(output_csv, fieldnames)
        return

    with open(output_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        old_fieldnames = reader.fieldnames or []
        if old_fieldnames == fieldnames:
            return
        old_rows = list(reader)

    keep_fields = {
        "task_id",
        "asset",
        "timeframe",
        "end_date",
        "end_time",
        "分析时的价格",
        "未来第一根K线的价格",
        "未来第二根K线的价格",
        "ai_decision",
        "is_correct",
        "cumulative_win_rate",
        "profit_loss_pct",
        "cumulative_profit_loss_pct",
        "duration_s",
        "result_id",
        "ai_version",
        "data_method",
        "kline_count",
        "future_kline_count",
        "error",
    }

    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in old_rows:
            new_row: Dict[str, Any] = {}
            for key in fieldnames:
                if key in keep_fields:
                    new_row[key] = row.get(key, "")
                else:
                    new_row[key] = ""
            writer.writerow(new_row)


def _ensure_output_header(output_csv: str, fieldnames: List[str]) -> None:
    if os.path.exists(output_csv) and os.path.getsize(output_csv) > 0:
        return
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def _append_output_row(output_csv: str, fieldnames: List[str], row: Dict[str, Any]) -> None:
    with open(output_csv, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow({k: row.get(k, "") for k in fieldnames})


def _post_with_retry(
    session: requests.Session,
    url: str,
    payload: Dict[str, Any],
    timeout_s: float,
    retries: int,
    backoff_s: float,
) -> Dict[str, Any]:
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            resp = session.post(url, json=payload, timeout=timeout_s)
            if resp.status_code >= 500:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_error = e
            if attempt >= retries:
                break
            sleep_s = backoff_s * (2**attempt)
            time.sleep(sleep_s)
    raise RuntimeError(str(last_error) if last_error else "Unknown request error")


def _run_one_task(
    base_url: str,
    analyze_path: str,
    timeout_s: float,
    retries: int,
    backoff_s: float,
    hold_threshold: float,
    row: Dict[str, str],
    defaults: Dict[str, Any],
) -> Dict[str, Any]:
    started = time.perf_counter()
    session = requests.Session()

    task_id = (row.get("task_id") or "").strip()
    asset = (row.get("asset") or "").strip()
    timeframe = (row.get("timeframe") or "").strip()
    end_date = (row.get("end_date") or "").strip()
    end_time = (row.get("end_time") or "").strip()

    data_method = (row.get("data_method") or defaults["data_method"]).strip()
    ai_version = (row.get("ai_version") or defaults["ai_version"]).strip()

    def get_int(name: str, default_value: int) -> int:
        raw = (row.get(name) or "").strip()
        if not raw:
            return int(default_value)
        return int(float(raw))

    kline_count = get_int("kline_count", defaults["kline_count"])
    future_kline_count = get_int("future_kline_count", defaults["future_kline_count"])

    payload: Dict[str, Any] = {
        "asset": asset,
        "timeframe": timeframe,
        "data_method": data_method,
        "kline_count": kline_count,
        "future_kline_count": future_kline_count,
        "ai_version": ai_version,
        "end_date": end_date,
        "end_time": end_time,
    }

    url = f"{base_url}{analyze_path}"
    try:
        result = _post_with_retry(
            session=session,
            url=url,
            payload=payload,
            timeout_s=timeout_s,
            retries=retries,
            backoff_s=backoff_s,
        )

        decision = result.get("decision") or {}
        action = _normalize_action(decision.get("action"))

        analysis_price = _try_parse_float(decision.get("entry_point"))
        if analysis_price is None:
            analysis_price = _try_parse_float(result.get("latest_price"))

        future_data = result.get("future_kline_data") or []
        future_close_1: Optional[float] = None
        future_close_2: Optional[float] = None
        if isinstance(future_data, list) and len(future_data) >= 1:
            future_close_1 = _extract_close(future_data[0]) if isinstance(future_data[0], dict) else None
        if isinstance(future_data, list) and len(future_data) >= 2:
            future_close_2 = _extract_close(future_data[1]) if isinstance(future_data[1], dict) else None

        change_1_pct: Optional[float] = None
        change_2_pct: Optional[float] = None
        if analysis_price is not None and analysis_price != 0:
            if future_close_1 is not None:
                change_1_pct = (future_close_1 - analysis_price) / analysis_price * 100.0
            if future_close_2 is not None:
                change_2_pct = (future_close_2 - analysis_price) / analysis_price * 100.0

        is_correct = _judge_prediction_two_kline(action, analysis_price, future_close_1, future_close_2)

        analysis_time_display = result.get("analysis_time_display") or f"{end_date} {end_time}:00"
        duration_s = round(time.perf_counter() - started, 3)

        return {
            "task_id": task_id,
            "asset": asset,
            "timeframe": timeframe,
            "end_date": end_date,
            "end_time": end_time,
            "分析时的价格": f"{analysis_price:.6f}" if analysis_price is not None else "N/A",
            "未来第一根K线的价格": (
                f"{future_close_1:.6f} {change_1_pct:+.2f}%"
                if future_close_1 is not None and change_1_pct is not None
                else (f"{future_close_1:.6f}" if future_close_1 is not None else "N/A")
            ),
            "未来第二根K线的价格": (
                f"{future_close_2:.6f} {change_2_pct:+.2f}%"
                if future_close_2 is not None and change_2_pct is not None
                else (f"{future_close_2:.6f}" if future_close_2 is not None else "N/A")
            ),
            "ai_decision": action,
            "is_correct": is_correct,
            "duration_s": duration_s,
            "result_id": result.get("result_id", ""),
            "ai_version": ai_version,
            "data_method": data_method,
            "kline_count": kline_count,
            "future_kline_count": future_kline_count,
            "error": "",
        }
    except Exception as e:
        duration_s = round(time.perf_counter() - started, 3)
        return {
            "task_id": task_id,
            "asset": asset,
            "timeframe": timeframe,
            "end_date": end_date,
            "end_time": end_time,
            "分析时的价格": "N/A",
            "未来第一根K线的价格": "N/A",
            "未来第二根K线的价格": "N/A",
            "ai_decision": "ERROR",
            "is_correct": "Error",
            "duration_s": duration_s,
            "result_id": "",
            "ai_version": ai_version,
            "data_method": data_method,
            "kline_count": kline_count,
            "future_kline_count": future_kline_count,
            "error": str(e),
        }


def _read_tasks(input_csv: str) -> List[Dict[str, str]]:
    with open(input_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("任务CSV缺少表头")
        missing = REQUIRED_TASK_FIELDS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"任务CSV缺少必需列: {', '.join(sorted(missing))}")
        tasks: List[Dict[str, str]] = []
        for row in reader:
            if not row:
                continue
            if not (row.get("asset") or "").strip():
                continue
            tasks.append({k: (v if v is not None else "") for k, v in row.items()})
        return tasks


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="批量回测：读取CSV任务列表，调用后端 analyze 接口并输出结果CSV")
    parser.add_argument("--backend", default="http://localhost:8000/api/v1", help="后端 API 基地址（默认 http://localhost:8000/api/v1）")
    parser.add_argument("--analyze-path", default="/analyze/", help="分析接口路径（默认 /analyze/）")
    parser.add_argument("--input", required=True, help="任务CSV路径（必填）")
    parser.add_argument("--output", default=os.path.join("tools", "backtest_results.csv"), help="输出CSV路径（默认 tools/backtest_results.csv）")
    parser.add_argument("--concurrency", type=int, default=3, help="并发数（默认 3）")
    parser.add_argument("--timeout", type=float, default=180.0, help="单次请求超时秒数（默认 180）")
    parser.add_argument("--retries", type=int, default=2, help="失败重试次数（默认 2）")
    parser.add_argument("--backoff", type=float, default=1.0, help="重试退避基准秒数（默认 1.0）")
    parser.add_argument("--hold-threshold", type=float, default=0.002, help="HOLD 判定阈值（默认 0.002=0.2%%）")
    parser.add_argument("--rerun", action="store_true", help="不跳过已存在结果，强制重跑")
    parser.add_argument("--default-kline-count", type=int, default=40, help="任务未填 kline_count 时默认值（默认 40）")
    parser.add_argument("--default-future-kline-count", type=int, default=13, help="任务未填 future_kline_count 时默认值（默认 13）")
    parser.add_argument("--default-ai-version", default="original", help="任务未填 ai_version 时默认值（默认 original）")
    parser.add_argument("--default-data-method", default="to_end", help="任务未填 data_method 时默认值（默认 to_end）")
    args = parser.parse_args(argv)

    input_csv = os.path.abspath(args.input)
    output_csv = os.path.abspath(args.output)

    if not os.path.exists(input_csv):
        print("任务CSV不存在：", input_csv, file=sys.stderr)
        print("必需列：task_id,asset,timeframe,end_date,end_time", file=sys.stderr)
        return 2

    base_url = _normalize_base_url(args.backend)
    analyze_path = args.analyze_path
    if not analyze_path.startswith("/"):
        analyze_path = "/" + analyze_path

    defaults = {
        "asset": "",
        "timeframe": "",
        "end_date": "",
        "end_time": "",
        "kline_count": args.default_kline_count,
        "future_kline_count": args.default_future_kline_count,
        "ai_version": args.default_ai_version,
        "data_method": args.default_data_method,
    }

    tasks = _read_tasks(input_csv)
    if not tasks:
        print("任务CSV为空或无有效任务行：", input_csv, file=sys.stderr)
        return 2

    fieldnames = [
        "task_id",
        "asset",
        "timeframe",
        "end_date",
        "end_time",
        "分析时的价格",
        "未来第一根K线的价格",
        "未来第二根K线的价格",
        "ai_decision",
        "is_correct",
        "cumulative_win_rate",
        "profit_loss_pct",
        "cumulative_profit_loss_pct",
        "duration_s",
        "result_id",
        "ai_version",
        "data_method",
        "kline_count",
        "future_kline_count",
        "error",
    ]

    existing_header, existing_keys = _load_existing_keys(output_csv)
    if existing_header and existing_header != fieldnames:
        print("检测到输出CSV表头已变更，正在原地迁移：", output_csv)
        _migrate_output_csv_in_place(output_csv, fieldnames)
        existing_header, existing_keys = _load_existing_keys(output_csv)

    _ensure_output_header(output_csv, fieldnames)

    to_run: List[Dict[str, str]] = []
    skipped = 0
    if args.rerun:
        to_run = tasks
    else:
        for row in tasks:
            try:
                key = _task_key_from_row(row, defaults)
            except Exception:
                to_run.append(row)
                continue
            if key in existing_keys:
                skipped += 1
                continue
            to_run.append(row)

    print(f"任务总数: {len(tasks)}，将执行: {len(to_run)}，跳过已存在: {skipped}")
    print(f"后端: {base_url}{analyze_path}")
    print(f"输出: {output_csv}")

    if not to_run:
        return 0

    completed = 0
    failed = 0
    stats_wins = 0
    stats_losses = 0

    with ThreadPoolExecutor(max_workers=max(1, int(args.concurrency))) as executor:
        futures = [
            executor.submit(
                _run_one_task,
                base_url,
                analyze_path,
                float(args.timeout),
                int(args.retries),
                float(args.backoff),
                float(args.hold_threshold),
                row,
                defaults,
            )
            for row in to_run
        ]

        for fut in as_completed(futures):
            result_row = fut.result()
            
            # 实时计算胜率
            is_correct = result_row.get("is_correct")
            if is_correct == "True":
                stats_wins += 1
            elif is_correct == "False":
                stats_losses += 1
            
            total_valid = stats_wins + stats_losses
            if total_valid > 0:
                win_rate = (stats_wins / total_valid) * 100.0
                result_row["cumulative_win_rate"] = f"{win_rate:.2f}%"
            else:
                result_row["cumulative_win_rate"] = "N/A"

            _append_output_row(output_csv, fieldnames, result_row)
            completed += 1
            if result_row.get("is_correct") == "Error":
                failed += 1

            task_id = result_row.get("task_id", "")
            asset = result_row.get("asset", "")
            timeframe = result_row.get("timeframe", "")
            date = f"{result_row.get('end_date', '')} {result_row.get('end_time', '')}"
            decision = result_row.get("ai_decision", "")
            correct = result_row.get("is_correct", "")
            win_rate_str = result_row.get("cumulative_win_rate", "N/A")
            
            print(f"[{completed}/{len(to_run)}] {task_id} {asset} {timeframe} {date} => {decision} ({correct}) [WinRate: {win_rate_str}]")

    print("-" * 60)
    print(f"执行完成 Summary:")
    print(f"总任务: {len(tasks)}")
    print(f"本次运行: {completed}")
    print(f"失败(Error): {failed}")
    
    total_valid = stats_wins + stats_losses
    if total_valid > 0:
        final_win_rate = (stats_wins / total_valid) * 100.0
        print(f"胜场: {stats_wins}")
        print(f"负场: {stats_losses}")
        print(f"胜率 (Win Rate): {final_win_rate:.2f}%  (计算公式: True / (True + False))")
    else:
        print("胜率 (Win Rate): N/A (无有效胜负结果)")
    print("-" * 60)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
