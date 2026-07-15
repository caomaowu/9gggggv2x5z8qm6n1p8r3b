import csv
import os
import random
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


REQUIRED_TASK_FIELDS = {"task_id", "asset", "timeframe", "end_date", "end_time"}


def _read_max_safe_workers() -> int:
    """Return the process-wide safety limit, with a conservative default."""
    try:
        return max(1, int(os.environ.get("BATCH_BACKTEST_MAX_WORKERS", "32")))
    except (TypeError, ValueError):
        return 32


MAX_SAFE_WORKERS = _read_max_safe_workers()


def effective_worker_count(requested: int, task_count: int) -> int:
    if task_count <= 0:
        return 0
    return min(max(1, int(requested)), task_count, MAX_SAFE_WORKERS)


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


def normalize_end_time(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    last_part = text.split()[-1]
    parts = last_part.split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return last_part


def normalize_end_date(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    
    # 去除可能的时间部分
    text = text.split(" ")[0].split("T")[0]
    
    # 替换常见分隔符
    text = text.replace("/", "-").replace(".", "-")
    
    parts = text.split("-")
    if len(parts) == 3:
        y, m, d = parts
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    
    return text



def normalize_base_url(base_url: str) -> str:
    base_url = base_url.strip()
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    return base_url


def parse_timeframes(value: Any, default_value: str) -> list[str]:
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    else:
        text = str(value or "").strip()
        if not text:
            text = str(default_value or "").strip()
        if not text:
            return []
        parts = [p.strip() for p in re.split(r"[+|,，、;；\s]+", text) if p and p.strip()]
        items = parts
    seen = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def task_key_from_row(row: Dict[str, str], defaults: Dict[str, Any]) -> TaskKey:
    def get_str(name: str, default_value: str) -> str:
        val = row.get(name)
        if val is None:
            val = ""
        value = str(val).strip()
        return value if value else str(default_value)

    def get_int(name: str, default_value: int) -> int:
        val = row.get(name)
        if val is None:
            return int(default_value)
        if isinstance(val, (int, float)):
            return int(val)
        raw = str(val).strip()
        if not raw:
            return int(default_value)
        return int(float(raw))

    timeframe_raw = row.get("timeframes") or row.get("timeframe")
    timeframes = parse_timeframes(timeframe_raw, defaults["timeframe"])
    timeframe_value = "+".join(timeframes) if len(timeframes) > 1 else (timeframes[0] if timeframes else "")

    return TaskKey(
        asset=get_str("asset", defaults["asset"]),
        timeframe=timeframe_value or get_str("timeframe", defaults["timeframe"]),
        end_date=normalize_end_date(get_str("end_date", defaults["end_date"])),
        end_time=normalize_end_time(get_str("end_time", defaults["end_time"])),
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


def _extract_high(item: Dict[str, Any]) -> Optional[float]:
    for key in ("high", "High", "h", "HIGH"):
        if key in item:
            parsed = _try_parse_float(item.get(key))
            if parsed is not None:
                return parsed
    return None


def _extract_low(item: Dict[str, Any]) -> Optional[float]:
    for key in ("low", "Low", "l", "LOW"):
        if key in item:
            parsed = _try_parse_float(item.get(key))
            if parsed is not None:
                return parsed
    return None


def _extract_brale_configs(result: Dict[str, Any]) -> Dict[str, str]:
    """从 API 响应 llm_config 中提取 Brale 三个 Agent 的模型名。

    返回字典，键名对应 .env 中的 BRALE_*_MODEL。
    """
    llm_config = result.get("llm_config") or {}
    configs: Dict[str, str] = {}
    for agent in ("indicator", "structure", "mechanics"):
        section = llm_config.get(agent) or {}
        configs[f"BRALE_{agent.upper()}_MODEL"] = str(section.get("model", "") or "")
    return configs


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


def _judge_prediction_single_kline(
    action: str,
    analysis_price: Optional[float],
    future_close: Optional[float],
) -> str:
    action = _normalize_action(action)

    if analysis_price is None or analysis_price == 0:
        return "NoBaselinePrice"

    if future_close is None:
        return "NoFutureData"

    if action not in {"LONG", "SHORT"}:
        return "未知"

    if action == "LONG":
        return "True" if future_close > analysis_price else "False"
    return "True" if future_close < analysis_price else "False"


def read_tasks(input_csv: str) -> List[Dict[str, str]]:
    with open(input_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("任务文件缺少表头")
        missing = REQUIRED_TASK_FIELDS - set(reader.fieldnames)
        if missing:
            raise ValueError(f"任务文件缺少必需列: {', '.join(sorted(missing))}")
        tasks: List[Dict[str, str]] = []
        for row in reader:
            if not row:
                continue
            if not (row.get("asset") or "").strip():
                continue
            tasks.append({k: (v if v is not None else "") for k, v in row.items()})
        return tasks


def load_existing_keys(output_csv: str) -> Tuple[Optional[List[str]], set]:
    if not os.path.exists(output_csv):
        return None, set()

    with open(output_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        keys = set()
        for row in reader:
            try:
                timeframe_raw = row.get("timeframes") or row.get("timeframe")
                timeframes = parse_timeframes(timeframe_raw, "")
                timeframe_value = "+".join(timeframes) if len(timeframes) > 1 else (timeframes[0] if timeframes else "")
                key = TaskKey(
                    asset=(row.get("asset") or "").strip(),
                    timeframe=timeframe_value or (row.get("timeframe") or "").strip(),
                    end_date=normalize_end_date((row.get("end_date") or row.get("date") or "").strip()),
                    end_time=normalize_end_time((row.get("end_time") or "").strip()),
                    data_method=(row.get("data_method") or row.get("data_method_short") or "to_end").strip(),
                    ai_version=(row.get("ai_version") or row.get("agent_version") or "original").strip(),
                    kline_count=int(float((row.get("kline_count") or "100").strip() or 100)),
                    future_kline_count=int(float((row.get("future_kline_count") or "13").strip() or 13)),
                )
                keys.add(key)
            except Exception:
                continue
        return header, keys


def migrate_output_csv_in_place(output_csv: str, fieldnames: List[str]) -> None:
    if not os.path.exists(output_csv) or os.path.getsize(output_csv) == 0:
        ensure_output_header(output_csv, fieldnames)
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
        "is_correct_1",
        "is_correct_2",
        "profit_pct_1",
        "profit_pct_2",
        "cumulative_win_rate",
        "cumulative_win_rate_1",
        "cumulative_win_rate_2",
        "duration_s",
        "result_id",
        "ai_version",
        "data_method",
        "kline_count",
        "future_kline_count",
        "error",
        "BRALE_INDICATOR_MODEL",
        "BRALE_STRUCTURE_MODEL",
        "BRALE_MECHANICS_MODEL",
        "回测模式",
        "资金_初始",
        "资金_当前",
        "下单金额",
        "仓位比例",
        "合约倍数",
        "滑点百分比",
        "强制平仓百分比",
        "名义金额",
        "成交数量",
        "成交开仓价",
        "成交平仓价",
        "平仓原因",
        "本次盈亏",
        "本次盈亏百分比",
    }

    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in old_rows:
            new_row: Dict[str, Any] = {}
            for key in fieldnames:
                new_row[key] = row.get(key, "") if key in keep_fields else ""
            writer.writerow(new_row)


def ensure_output_header(output_csv: str, fieldnames: List[str]) -> None:
    if os.path.exists(output_csv) and os.path.getsize(output_csv) > 0:
        return
    os.makedirs(os.path.dirname(os.path.abspath(output_csv)), exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()


def append_output_row(output_csv: str, fieldnames: List[str], row: Dict[str, Any]) -> None:
    with open(output_csv, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writerow({k: row.get(k, "") for k in fieldnames})
        f.flush()


class CsvWriter:
    """线程安全且可确认的 CSV 写入器。

    write() 成功返回即代表该行已交给操作系统；stop() 会完成最终落盘确认。
    写入错误直接反馈给主流程，不再由 daemon 写线程静默丢失。
    """

    def __init__(self, output_csv: str, fieldnames: List[str]):
        self.output_csv = output_csv
        self.fieldnames = list(fieldnames)
        self._lock = threading.Lock()
        self._file: Any = None
        self._writer: Optional[csv.DictWriter] = None
        self._started = False
        self.rows_written = 0

    def start(self) -> None:
        with self._lock:
            if self._started:
                raise RuntimeError("CSV 写入器已经启动")
            os.makedirs(os.path.dirname(os.path.abspath(self.output_csv)), exist_ok=True)
            self._file = open(self.output_csv, "a", encoding="utf-8", newline="")
            self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames)
            self._started = True

    def write(self, row: Dict[str, Any]) -> None:
        with self._lock:
            if not self._started or self._file is None or self._writer is None:
                raise RuntimeError("CSV 写入器未启动或已经停止")
            try:
                self._writer.writerow({k: row.get(k, "") for k in self.fieldnames})
                self._file.flush()
                self.rows_written += 1
            except Exception as exc:
                raise RuntimeError(f"CSV 第 {self.rows_written + 1} 行写入失败: {exc}") from exc

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            file_obj = self._file
            self._file = None
            self._writer = None
            self._started = False
            try:
                if file_obj is not None:
                    file_obj.flush()
                    os.fsync(file_obj.fileno())
            finally:
                if file_obj is not None:
                    file_obj.close()

    def __enter__(self) -> "CsvWriter":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.stop()


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
            delay = backoff_s * (2**attempt)
            time.sleep(delay + random.uniform(0.0, max(0.0, delay * 0.25)))
    raise RuntimeError(str(last_error) if last_error else "请求失败")


def run_one_task(
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

    task_id = (row.get("task_id") or "").strip()
    asset = (row.get("asset") or "").strip()
    timeframe_raw = row.get("timeframes") or row.get("timeframe")
    timeframes = parse_timeframes(timeframe_raw, defaults["timeframe"])
    timeframe = "+".join(timeframes) if len(timeframes) > 1 else (timeframes[0] if timeframes else "")
    end_date = normalize_end_date((row.get("end_date") or "").strip())
    end_time = normalize_end_time((row.get("end_time") or "").strip())

    data_method = (row.get("data_method") or defaults["data_method"]).strip()
    ai_version = (row.get("ai_version") or defaults["ai_version"]).strip()

    def get_int(name: str, default_value: int) -> int:
        val = row.get(name)
        if val is None:
            return int(default_value)
        if isinstance(val, (int, float)):
            return int(val)
        raw = str(val).strip()
        if not raw:
            return int(default_value)
        return int(float(raw))

    kline_count = get_int("kline_count", defaults["kline_count"])
    future_kline_count = get_int("future_kline_count", defaults["future_kline_count"])

    payload: Dict[str, Any] = {
        "asset": asset,
        "data_method": data_method,
        "kline_count": kline_count,
        "future_kline_count": future_kline_count,
        "ai_version": ai_version,
        "end_date": end_date,
        "end_time": end_time,
    }
    if len(timeframes) > 1:
        payload["timeframe"] = timeframes
        payload["multi_timeframe_mode"] = True
        payload["timeframes"] = timeframes
    else:
        payload["timeframe"] = timeframe

    url = f"{base_url}{analyze_path}"
    session = requests.Session()
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

        is_correct_1 = _judge_prediction_single_kline(action, analysis_price, future_close_1)
        is_correct_2 = _judge_prediction_single_kline(action, analysis_price, future_close_2)

        profit_pct_1_str = "N/A"
        profit_pct_2_str = "N/A"
        if analysis_price is not None and analysis_price != 0:
            if future_close_1 is not None:
                raw_pct_1 = (future_close_1 - analysis_price) / analysis_price * 100.0
                if action == "LONG":
                    profit_pct_1_str = f"{raw_pct_1:+.2f}%"
                elif action == "SHORT":
                    profit_pct_1_str = f"{-raw_pct_1:+.2f}%"
            if future_close_2 is not None:
                raw_pct_2 = (future_close_2 - analysis_price) / analysis_price * 100.0
                if action == "LONG":
                    profit_pct_2_str = f"{raw_pct_2:+.2f}%"
                elif action == "SHORT":
                    profit_pct_2_str = f"{-raw_pct_2:+.2f}%"

        duration_s = round(time.perf_counter() - started, 3)

        # 逆势波动提取（仅预测正确时存在）
        adverse_exc = result.get("adverse_excursion") or {}
        adverse_has = "是" if (adverse_exc and adverse_exc.get("violations")) else ("否" if adverse_exc else "")
        adverse_count = len(adverse_exc.get("violations") or []) if adverse_exc else 0
        adverse_max_pct = ""
        if adverse_exc:
            violations = adverse_exc.get("violations") or []
            if violations:
                max_dev = max(abs(v.get("deviation_pct", 0)) for v in violations)
                adverse_max_pct = f"{max_dev:.2f}%"

        # Agent 分数提取
        fusion_raw = result.get("decision", {}).get("fusion_raw") or {}
        indicator_sum = result.get("indicator_summary") or {}
        structure_sum = result.get("structure_summary") or {}
        mechanics_sum = result.get("mechanics_summary") or {}

        fusion_score = round(float(fusion_raw.get("score", 0)), 4) if fusion_raw else ""
        fusion_confidence = round(float(fusion_raw.get("confidence", 0)), 4) if fusion_raw else ""
        indicator_score = round(float(indicator_sum.get("movement_score", 0)), 4) if indicator_sum else ""
        structure_score = round(float(structure_sum.get("movement_score", 0)), 4) if structure_sum else ""
        mechanics_score = round(float(mechanics_sum.get("movement_score", 0)), 4) if mechanics_sum else ""

        # Agent 独立验证（预测方向 vs 实际方向）
        agent_ver = result.get("agent_verification") or {}
        agents = agent_ver.get("agents") or {}
        def _matched_str(key):
            v = agents.get(key, {}).get("matched")
            if v is True: return "是"
            if v is False: return "否"
            return ""

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
            "is_correct": is_correct_2 if is_correct_2 else "",
            "is_correct_1": is_correct_1 if is_correct_1 else "",
            "is_correct_2": is_correct_2 if is_correct_2 else "",
            "profit_pct_1": profit_pct_1_str,
            "profit_pct_2": profit_pct_2_str,
            "cumulative_win_rate_1": "",
            "cumulative_win_rate_2": "",
            "duration_s": duration_s,
            "result_id": result.get("result_id", ""),
            "ai_version": ai_version,
            "data_method": data_method,
            "kline_count": kline_count,
            "future_kline_count": future_kline_count,
            "error": "",
            **_extract_brale_configs(result),
            "逆势_有偏离": adverse_has,
            "逆势_偏离次数": adverse_count,
            "逆势_最大偏离%": adverse_max_pct,
            "fusion_score": fusion_score,
            "fusion_confidence": fusion_confidence,
            "indicator_score": indicator_score,
            "structure_score": structure_score,
            "mechanics_score": mechanics_score,
            "indicator_匹配": _matched_str("indicator"),
            "structure_匹配": _matched_str("structure"),
            "mechanics_匹配": _matched_str("mechanics"),
            "fusion_匹配": _matched_str("fusion"),
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
            "is_correct_1": "Error",
            "is_correct_2": "Error",
            "profit_pct_1": "N/A",
            "profit_pct_2": "N/A",
            "cumulative_win_rate_1": "",
            "cumulative_win_rate_2": "",
            "duration_s": duration_s,
            "result_id": "",
            "ai_version": ai_version,
            "data_method": data_method,
            "kline_count": kline_count,
            "future_kline_count": future_kline_count,
            "error": str(e),
            "BRALE_INDICATOR_MODEL": "",
            "BRALE_STRUCTURE_MODEL": "",
            "BRALE_MECHANICS_MODEL": "",
            "逆势_有偏离": "",
            "逆势_偏离次数": "",
            "逆势_最大偏离%": "",
            "fusion_score": "",
            "fusion_confidence": "",
            "indicator_score": "",
            "structure_score": "",
            "mechanics_score": "",
            "indicator_匹配": "",
            "structure_匹配": "",
            "mechanics_匹配": "",
            "fusion_匹配": "",
        }
    finally:
        session.close()


def _should_use_aggressive_mode(
    *,
    position_state: Dict[str, Any],
    equity_pct: float,
    initial_equity: float,
    aggressive_threshold_pct: float,
    conservative_threshold_pct: float,
) -> bool:
    """
    判断是否应该使用激进模式。

    策略逻辑：
    1. 如果已经在激进模式，必须跌破保守阈值才回到保守模式
    2. 如果在保守模式，必须达到激进阈值才进入激进模式
    3. 这样可以避免频繁切换

    Args:
        position_state: 当前仓位状态，包含 is_aggressive 标志
        equity_pct: 当前资金相对初始本金的百分比
        initial_equity: 初始本金
        aggressive_threshold_pct: 进入激进模式的阈值（百分比）
        conservative_threshold_pct: 回到保守模式的阈值（百分比）

    Returns:
        bool: True 表示使用激进模式，False 表示使用保守模式
    """
    is_aggressive = position_state.get("is_aggressive", False)

    if is_aggressive:
        # 已经在激进模式，必须跌破保守阈值才回到保守
        return equity_pct >= conservative_threshold_pct
    else:
        # 在保守模式，必须达到激进阈值才进入激进
        return equity_pct >= aggressive_threshold_pct


def run_one_task_with_funds(
    *,
    base_url: str,
    analyze_path: str,
    timeout_s: float,
    retries: int,
    backoff_s: float,
    hold_threshold: float,
    row: Dict[str, str],
    defaults: Dict[str, Any],
    initial_equity: float,
    equity_before: float,
    position_mode: str = "固定百分比",
    allocation_pct: float = 100.0,
    fixed_amount: float = 1000.0,
    contract_multiplier: float,
    slippage_pct: float,
    force_close_pct: float,
    trigger_order: str,
    # 阶梯仓位策略参数
    position_state: Optional[Dict[str, Any]] = None,
    conservative_base_ratio: float = 30.0,
    aggressive_threshold_pct: float = 150.0,
    conservative_threshold_pct: float = 110.0,
    use_aggressive_mode_only_profit: bool = True,
) -> tuple[Dict[str, Any], float]:
    started = time.perf_counter()

    # 初始化仓位状态
    if position_state is None:
        position_state = {"is_aggressive": False}

    task_id = (row.get("task_id") or "").strip()
    asset = (row.get("asset") or "").strip()
    timeframe_raw = row.get("timeframes") or row.get("timeframe")
    timeframes = parse_timeframes(timeframe_raw, defaults["timeframe"])
    timeframe = "+".join(timeframes) if len(timeframes) > 1 else (timeframes[0] if timeframes else "")
    end_date = normalize_end_date((row.get("end_date") or "").strip())
    end_time = normalize_end_time((row.get("end_time") or "").strip())

    data_method = (row.get("data_method") or defaults["data_method"]).strip()
    ai_version = (row.get("ai_version") or defaults["ai_version"]).strip()

    def get_int(name: str, default_value: int) -> int:
        val = row.get(name)
        if val is None:
            return int(default_value)
        if isinstance(val, (int, float)):
            return int(val)
        raw = str(val).strip()
        if not raw:
            return int(default_value)
        return int(float(raw))

    kline_count = get_int("kline_count", defaults["kline_count"])
    future_kline_count = get_int("future_kline_count", defaults["future_kline_count"])

    payload: Dict[str, Any] = {
        "asset": asset,
        "data_method": data_method,
        "kline_count": kline_count,
        "future_kline_count": future_kline_count,
        "ai_version": ai_version,
        "end_date": end_date,
        "end_time": end_time,
    }
    if len(timeframes) > 1:
        payload["timeframe"] = timeframes
        payload["multi_timeframe_mode"] = True
        payload["timeframes"] = timeframes
    else:
        payload["timeframe"] = timeframe

    url = f"{base_url}{analyze_path}"
    session = requests.Session()
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

        is_correct_1 = _judge_prediction_single_kline(action, analysis_price, future_close_1)
        is_correct_2 = _judge_prediction_single_kline(action, analysis_price, future_close_2)

        profit_pct_1_str = "N/A"
        profit_pct_2_str = "N/A"
        if analysis_price is not None and analysis_price != 0:
            if future_close_1 is not None:
                raw_pct_1 = (future_close_1 - analysis_price) / analysis_price * 100.0
                if action == "LONG":
                    profit_pct_1_str = f"{raw_pct_1:+.2f}%"
                elif action == "SHORT":
                    profit_pct_1_str = f"{-raw_pct_1:+.2f}%"
            if future_close_2 is not None:
                raw_pct_2 = (future_close_2 - analysis_price) / analysis_price * 100.0
                if action == "LONG":
                    profit_pct_2_str = f"{raw_pct_2:+.2f}%"
                elif action == "SHORT":
                    profit_pct_2_str = f"{-raw_pct_2:+.2f}%"

        slippage = max(0.0, float(slippage_pct)) / 100.0
        force_pct = max(0.0, float(force_close_pct)) / 100.0
        alloc = min(max(0.0, float(allocation_pct)) / 100.0, 1.0)
        multiplier = max(0.0, float(contract_multiplier))

        equity_after = float(equity_before)
        order_amount = 0.0
        notional = 0.0
        qty = 0.0
        entry_exec = None
        exit_exec = None
        pnl = 0.0
        pnl_pct = None
        exit_reason = ""

        if action not in {"LONG", "SHORT"}:
            exit_reason = "不交易"
        elif analysis_price is None or analysis_price <= 0:
            exit_reason = "无分析价格"
        elif not isinstance(future_data, list) or len(future_data) < 2:
            exit_reason = "未来K线不足"
        else:
            k1 = future_data[0] if isinstance(future_data[0], dict) else {}
            k2 = future_data[1] if isinstance(future_data[1], dict) else {}

            k1_high = _extract_high(k1)
            k1_low = _extract_low(k1)
            k2_high = _extract_high(k2)
            k2_low = _extract_low(k2)

            if future_close_2 is None:
                exit_reason = "无平仓价格"
            else:
                baseline = float(analysis_price)
                p_up = baseline * (1.0 + force_pct)
                p_dn = baseline * (1.0 - force_pct)

                def pick_forced_exit(
                    *,
                    high: Optional[float],
                    low: Optional[float],
                    index: int,
                ) -> Optional[tuple[float, str]]:
                    if high is None or low is None:
                        return None

                    if action == "LONG":
                        hit_profit = high >= p_up
                        hit_loss = low <= p_dn
                        if hit_profit and hit_loss:
                            if trigger_order == "乐观（先有利）":
                                return p_up, f"强制平仓-盈利-第{index}根"
                            return p_dn, f"强制平仓-亏损-第{index}根"
                        if hit_loss:
                            return p_dn, f"强制平仓-亏损-第{index}根"
                        if hit_profit:
                            return p_up, f"强制平仓-盈利-第{index}根"
                        return None

                    hit_profit = low <= p_dn
                    hit_loss = high >= p_up
                    if hit_profit and hit_loss:
                        if trigger_order == "乐观（先有利）":
                            return p_dn, f"强制平仓-盈利-第{index}根"
                        return p_up, f"强制平仓-亏损-第{index}根"
                    if hit_loss:
                        return p_up, f"强制平仓-亏损-第{index}根"
                    if hit_profit:
                        return p_dn, f"强制平仓-盈利-第{index}根"
                    return None

                forced = pick_forced_exit(high=k1_high, low=k1_low, index=1)
                if forced is None:
                    forced = pick_forced_exit(high=k2_high, low=k2_low, index=2)

                exit_raw = None
                if forced is not None:
                    exit_raw, exit_reason = forced
                else:
                    exit_raw = float(future_close_2)
                    exit_reason = "按第2根收盘平仓"

                if action == "LONG":
                    entry_exec = baseline * (1.0 + slippage)
                    exit_exec = float(exit_raw) * (1.0 - slippage)
                else:
                    entry_exec = baseline * (1.0 - slippage)
                    exit_exec = float(exit_raw) * (1.0 + slippage)

                # 根据策略计算下单金额
                if position_mode == "阶梯仓位":
                    # 计算当前资金相对初始本金的百分比（防止除零）
                    if float(initial_equity) == 0:
                        equity_pct = 100.0  # 如果初始本金为0，视为100%
                    else:
                        equity_pct = (float(equity_before) / float(initial_equity)) * 100.0

                    # 判断是否应该使用激进模式
                    is_aggressive = _should_use_aggressive_mode(
                        position_state=position_state,
                        equity_pct=equity_pct,
                        initial_equity=float(initial_equity),
                        aggressive_threshold_pct=aggressive_threshold_pct,
                        conservative_threshold_pct=conservative_threshold_pct,
                    )

                    # 更新状态
                    position_state["is_aggressive"] = is_aggressive

                    # 计算下单金额
                    if is_aggressive and use_aggressive_mode_only_profit:
                        # 激进模式：只用盈利部分
                        profit = float(equity_before) - float(initial_equity)
                        if profit > 0:
                            order_amount = profit  # 盈利部分全仓
                        else:
                            # 盈利亏完，自动回到保守模式
                            order_amount = float(equity_before) * conservative_base_ratio / 100.0
                            position_state["is_aggressive"] = False
                    else:
                        # 保守模式：使用基础比例
                        order_amount = float(equity_before) * conservative_base_ratio / 100.0

                elif position_mode == "固定百分比":
                    order_amount = float(equity_before) * alloc
                else:  # 固定金额
                    # 固定金额，但不超过当前资金
                    order_amount = min(float(fixed_amount), float(equity_before))
                notional = order_amount * multiplier
                qty = (notional / entry_exec) if entry_exec and entry_exec > 0 else 0.0

                if action == "LONG":
                    pnl = (exit_exec - entry_exec) * qty
                else:
                    pnl = (entry_exec - exit_exec) * qty

                equity_after = float(equity_before) + pnl
                pnl_pct = (pnl / float(equity_before) * 100.0) if float(equity_before) != 0 else None

        duration_s = round(time.perf_counter() - started, 3)

        result_row: Dict[str, Any] = {
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
            "is_correct": is_correct_2 if is_correct_2 else "",
            "is_correct_1": is_correct_1 if is_correct_1 else "",
            "is_correct_2": is_correct_2 if is_correct_2 else "",
            "profit_pct_1": profit_pct_1_str,
            "profit_pct_2": profit_pct_2_str,
            "cumulative_win_rate_1": "",
            "cumulative_win_rate_2": "",
            "duration_s": duration_s,
            "result_id": result.get("result_id", ""),
            "ai_version": ai_version,
            "data_method": data_method,
            "kline_count": kline_count,
            "future_kline_count": future_kline_count,
            "error": "",
            "资金_初始": f"{float(initial_equity):.2f}",
            "资金_当前": f"{float(equity_after):.2f}",
            "下单金额": f"{float(order_amount):.2f}",
            "仓位比例": f"{alloc * 100.0:.2f}%" if position_mode != "阶梯仓位" else f"{(float(order_amount) / float(equity_before) * 100.0) if equity_before > 0 else 0:.2f}%",
            "合约倍数": f"{multiplier:.4f}",
            "滑点百分比": f"{float(slippage_pct):.4f}%",
            "强制平仓百分比": f"{float(force_close_pct):.4f}%",
            "名义金额": f"{float(notional):.2f}",
            "成交数量": f"{float(qty):.8f}",
            "成交开仓价": f"{float(entry_exec):.6f}" if entry_exec is not None else "N/A",
            "成交平仓价": f"{float(exit_exec):.6f}" if exit_exec is not None else "N/A",
            "平仓原因": exit_reason,
            "本次盈亏": f"{float(pnl):+.2f}",
            "本次盈亏百分比": f"{float(pnl_pct):+.2f}%" if pnl_pct is not None else "N/A",
            **_extract_brale_configs(result),
        }

        # 添加仓位状态到返回结果
        result_row["_is_aggressive"] = position_state.get("is_aggressive", False)

        return result_row, float(equity_after)
    except Exception as e:
        duration_s = round(time.perf_counter() - started, 3)
        result_row = {
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
            "is_correct_1": "Error",
            "is_correct_2": "Error",
            "profit_pct_1": "N/A",
            "profit_pct_2": "N/A",
            "cumulative_win_rate_1": "",
            "cumulative_win_rate_2": "",
            "duration_s": duration_s,
            "result_id": "",
            "ai_version": ai_version,
            "data_method": data_method,
            "kline_count": kline_count,
            "future_kline_count": future_kline_count,
            "error": str(e),
            "资金_初始": f"{float(initial_equity):.2f}",
            "资金_当前": f"{float(equity_before):.2f}",
            "下单金额": f"{float(equity_before) * min(max(0.0, float(allocation_pct)), 100.0) / 100.0:.2f}",
            "仓位比例": f"{min(max(0.0, float(allocation_pct)), 100.0):.2f}%",
            "合约倍数": f"{max(0.0, float(contract_multiplier)):.4f}",
            "滑点百分比": f"{max(0.0, float(slippage_pct)):.4f}%",
            "强制平仓百分比": f"{max(0.0, float(force_close_pct)):.4f}%",
            "名义金额": "0.00",
            "成交数量": "0.00000000",
            "成交开仓价": "N/A",
            "成交平仓价": "N/A",
            "平仓原因": "执行失败",
            "本次盈亏": "+0.00",
            "本次盈亏百分比": "N/A",
            "BRALE_INDICATOR_MODEL": "",
            "BRALE_STRUCTURE_MODEL": "",
            "BRALE_MECHANICS_MODEL": "",
        }
        # 添加仓位状态到返回结果（异常情况下保持当前状态）
        result_row["_is_aggressive"] = position_state.get("is_aggressive", False)
        return result_row, float(equity_before)
    finally:
        session.close()


def run_tasks_concurrently(
    base_url: str,
    analyze_path: str,
    timeout_s: float,
    retries: int,
    backoff_s: float,
    hold_threshold: float,
    rows: List[Dict[str, str]],
    defaults: Dict[str, Any],
    *,
    max_workers: int,
):
    worker_count = effective_worker_count(max_workers, len(rows))
    if worker_count == 0:
        return

    def submit(executor: ThreadPoolExecutor, row: Dict[str, str]) -> Future:
        return executor.submit(
            run_one_task,
            base_url,
            analyze_path,
            timeout_s,
            retries,
            backoff_s,
            hold_threshold,
            row,
            defaults,
        )

    row_iterator = iter(rows)
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="backtest") as executor:
        pending: Dict[Future, Dict[str, str]] = {}
        for _ in range(worker_count):
            try:
                row = next(row_iterator)
            except StopIteration:
                break
            pending[submit(executor, row)] = row

        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                row = pending.pop(future)
                try:
                    yield future.result()
                except Exception as exc:
                    yield _unexpected_failure_row(row, defaults, exc)

                try:
                    next_row = next(row_iterator)
                except StopIteration:
                    continue
                pending[submit(executor, next_row)] = next_row


def _unexpected_failure_row(
    row: Dict[str, str], defaults: Dict[str, Any], exc: Exception
) -> Dict[str, Any]:
    timeframe_raw = row.get("timeframes") or row.get("timeframe")
    timeframes = parse_timeframes(timeframe_raw, str(defaults.get("timeframe", "")))
    timeframe = "+".join(timeframes) if len(timeframes) > 1 else (timeframes[0] if timeframes else "")

    def safe_int(name: str, fallback: int) -> int:
        try:
            return int(float(row.get(name) or defaults.get(name) or fallback))
        except (TypeError, ValueError):
            return fallback

    return {
        "task_id": str(row.get("task_id") or "").strip(),
        "asset": str(row.get("asset") or "").strip(),
        "timeframe": timeframe,
        "end_date": normalize_end_date(row.get("end_date")),
        "end_time": normalize_end_time(row.get("end_time")),
        "分析时的价格": "N/A",
        "未来第一根K线的价格": "N/A",
        "未来第二根K线的价格": "N/A",
        "ai_decision": "ERROR",
        "is_correct": "Error",
        "is_correct_1": "Error",
        "is_correct_2": "Error",
        "profit_pct_1": "N/A",
        "profit_pct_2": "N/A",
        "cumulative_win_rate_1": "",
        "cumulative_win_rate_2": "",
        "duration_s": 0.0,
        "result_id": "",
        "ai_version": str(row.get("ai_version") or defaults.get("ai_version") or "").strip(),
        "data_method": str(row.get("data_method") or defaults.get("data_method") or "").strip(),
        "kline_count": safe_int("kline_count", 100),
        "future_kline_count": safe_int("future_kline_count", 13),
        "error": f"任务线程异常: {exc}",
        "BRALE_INDICATOR_MODEL": "",
        "BRALE_STRUCTURE_MODEL": "",
        "BRALE_MECHANICS_MODEL": "",
    }
