import re
from datetime import datetime, timedelta
from typing import Any, MutableMapping

import pandas as pd


PAGES = ["任务来源", "执行回测", "结果"]

OUTPUT_FIELDNAMES = [
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
    "AGENT_MODEL",
    "GRAPH_MODEL",
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
    # 逆势波动验证（仅预测正确时统计）
    "逆势_有偏离",
    "逆势_偏离次数",
    "逆势_最大偏离%",
    # Agent 分数
    "fusion_score",
    "fusion_confidence",
    "indicator_score",
    "structure_score",
    "mechanics_score",
    # Agent 独立验证（预测方向 vs 实际方向）
    "indicator_匹配",
    "structure_匹配",
    "mechanics_匹配",
    "fusion_匹配",
]

DEFAULT_EXECUTE_DISPLAY_COLS = [
    "task_id",
    "asset",
    "timeframe",
    "end_date",
    "end_time",
    "ai_decision",
    "is_correct",
    "is_correct_1",
    "is_correct_2",
    "profit_pct_1",
    "profit_pct_2",
    "cumulative_win_rate",
    "cumulative_win_rate_1",
    "cumulative_win_rate_2",
    "下单金额",
    "资金_当前",
    "本次盈亏百分比",
    "逆势_偏离次数",
    "逆势_最大偏离%",
    "fusion_score",
    "fusion_confidence",
    "indicator_匹配",
    "structure_匹配",
    "mechanics_匹配",
    "fusion_匹配",
]

DEFAULT_RESULTS_DISPLAY_COLS = [
    "task_id",
    "asset",
    "timeframe",
    "end_date",
    "end_time",
    "ai_decision",
    "is_correct",
    "is_correct_1",
    "is_correct_2",
    "profit_pct_1",
    "profit_pct_2",
    "cumulative_win_rate",
    "cumulative_win_rate_1",
    "cumulative_win_rate_2",
    "下单金额",
    "资金_当前",
    "本次盈亏百分比",
    "逆势_偏离次数",
    "逆势_最大偏离%",
    "fusion_score",
    "fusion_confidence",
    "indicator_匹配",
    "structure_匹配",
    "mechanics_匹配",
    "fusion_匹配",
]


def init_session_state(state: MutableMapping[str, Any]) -> None:
    state.setdefault("tasks", [])
    state.setdefault("active_page", PAGES[0])
    state.setdefault("next_page", None)
    state.setdefault("bt_last_output_csv", "")
    state.setdefault("bt_last_summary", None)
    state.setdefault("bt_last_rows", [])
    state.setdefault("gen_assets_input", "BTCUSDT, ETHUSDT, SOLUSDT")


def normalize_asset_token(token: str) -> str:
    text = (token or "").strip()
    if not text:
        return ""

    text = (
        text.replace("，", ",")
        .replace("、", ",")
        .replace("；", ",")
        .replace(";", ",")
        .replace("／", "/")
        .replace("－", "-")
    )
    text = re.sub(r"\s+", "", text).upper()

    if "/" in text:
        base, quote = text.split("/", 1)
        if base and quote:
            text = f"{base}{quote}"

    if text.count("-") == 1 and text.endswith("USDT"):
        base, quote = text.split("-", 1)
        if quote == "USDT" and base:
            text = f"{base}{quote}"

    if "-" in text:
        return text

    if not text.endswith("USDT"):
        text = f"{text}USDT"

    return text


def parse_assets_input(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []

    parts = re.split(r"[\s,，、;；\n\r\t]+", text)
    assets: list[str] = []
    seen = set()
    for part in parts:
        normalized = normalize_asset_token(part)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        assets.append(normalized)
    return assets


def normalize_assets_input_text(raw: str) -> str:
    assets = parse_assets_input(raw)
    return ", ".join(assets) if assets else (raw or "")


def style_df(df: pd.DataFrame) -> Any:
    def color_is_correct_col(col: pd.Series) -> list[str]:
        colors = []
        for val in col:
            s_val = str(val).upper()
            if s_val == "TRUE":
                colors.append("color: #28a745; font-weight: bold")
            elif s_val == "FALSE":
                colors.append("color: #dc3545; font-weight: bold")
            else:
                colors.append("")
        return colors

    def color_profit_col(col: pd.Series) -> list[str]:
        colors = []
        for val in col:
            s_val = str(val)
            if s_val.startswith("+"):
                colors.append("color: #28a745; font-weight: bold")
            elif s_val.startswith("-"):
                colors.append("color: #dc3545; font-weight: bold")
            else:
                colors.append("")
        return colors

    styler = df.style
    if "is_correct" in df.columns:
        styler = styler.apply(color_is_correct_col, subset=["is_correct"])
    if "is_correct_1" in df.columns:
        styler = styler.apply(color_is_correct_col, subset=["is_correct_1"])
    if "is_correct_2" in df.columns:
        styler = styler.apply(color_is_correct_col, subset=["is_correct_2"])
    if "profit_pct_1" in df.columns:
        styler = styler.apply(color_profit_col, subset=["profit_pct_1"])
    if "profit_pct_2" in df.columns:
        styler = styler.apply(color_profit_col, subset=["profit_pct_2"])
    return styler


def generate_tasks_random(
    assets: list[str],
    timeframe: str,
    count_per_asset: int,
    start_dt: datetime,
    end_dt: datetime,
    *,
    default_kline_count: int,
    default_future_kline_count: int,
    default_ai_version: str,
    default_data_method: str,
    uuid_factory,
    rand_int,
) -> list[dict[str, Any]]:
    generated_tasks: list[dict[str, Any]] = []
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    for asset in assets:
        for _ in range(count_per_asset):
            random_ts = rand_int(start_ts, end_ts)
            dt = datetime.fromtimestamp(random_ts)
            generated_tasks.append(
                {
                    "task_id": f"gen_{uuid_factory()}",
                    "asset": asset,
                    "timeframe": timeframe,
                    "end_date": dt.strftime("%Y-%m-%d"),
                    "end_time": dt.strftime("%H:%M"),
                    "kline_count": default_kline_count,
                    "future_kline_count": default_future_kline_count,
                    "ai_version": default_ai_version,
                    "data_method": default_data_method,
                }
            )

    return generated_tasks


def generate_tasks_cycle_end(
    assets: list[str],
    timeframe: str,
    sample_count: int,
    start_dt: datetime,
    end_dt: datetime,
    *,
    default_kline_count: int,
    default_future_kline_count: int,
    default_ai_version: str,
    default_data_method: str,
    uuid_factory,
    rand_sample,
    rand_int,
) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    generated_tasks: list[dict[str, Any]] = []

    cycle_offsets: list[int] = []
    
    # 尝试解析主周期（支持 4h+15m 这种格式，取第一个作为主周期）
    # 分隔符支持 + , | 空格
    separators = ["+", ",", "|", " "]
    main_tf = timeframe
    for sep in separators:
        if sep in main_tf:
            main_tf = main_tf.split(sep)[0]
            break
    main_tf = main_tf.strip()

    if main_tf == "4h":
        cycle_offsets = [4, 8, 12, 16, 20, 24]
    elif main_tf == "1h":
        cycle_offsets = list(range(1, 25))
    else:
        errors.append(f"周期末端模式暂不支持 {timeframe} (识别为主周期: {main_tf})，仅支持 1h 和 4h")
        return [], errors

    for asset in assets:
        candidates: list[datetime] = []
        iter_day = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_day_limit = end_dt

        while iter_day < end_day_limit:
            for offset in cycle_offsets:
                cycle_end_dt = iter_day + timedelta(hours=offset)
                if cycle_end_dt <= start_dt:
                    continue
                if cycle_end_dt > end_dt:
                    break
                window_start = cycle_end_dt - timedelta(minutes=5)
                final_dt = window_start + timedelta(minutes=rand_int(0, 4))
                candidates.append(final_dt)
            iter_day += timedelta(days=1)

        if not candidates:
            continue

        selected_dts = candidates if len(candidates) <= sample_count else rand_sample(candidates, sample_count)
        for dt in selected_dts:
            generated_tasks.append(
                {
                    "task_id": f"end_{timeframe}_{dt.strftime('%Y%m%d%H%M')}_{uuid_factory()[:4]}",
                    "asset": asset,
                    "timeframe": timeframe,
                    "end_date": dt.strftime("%Y-%m-%d"),
                    "end_time": dt.strftime("%H:%M"),
                    "kline_count": default_kline_count,
                    "future_kline_count": default_future_kline_count,
                    "ai_version": default_ai_version,
                    "data_method": default_data_method,
                }
            )

    return generated_tasks, errors


def classify_is_correct(val: Any) -> str:
    if val is True:
        return "True"
    if val is False:
        return "False"
    if val is None:
        return ""
    text = str(val).strip()
    if not text:
        return ""
    upper = text.upper()
    if upper == "TRUE":
        return "True"
    if upper == "FALSE":
        return "False"
    if upper == "ERROR":
        return "Error"
    return text


def compute_summary_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    wins_1 = 0
    losses_1 = 0
    wins_2 = 0
    losses_2 = 0
    failed = 0
    funds_initial = None
    funds_final = None

    def _try_parse_float(v: Any) -> Any:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:
            return None

    for row in rows:
        v1_raw = row.get("is_correct_1")
        v2_raw = row.get("is_correct_2")

        v1 = classify_is_correct(v1_raw if v1_raw not in (None, "") else row.get("is_correct"))
        v2 = classify_is_correct(v2_raw if v2_raw not in (None, "") else row.get("is_correct"))

        if v1 == "True":
            wins_1 += 1
        elif v1 == "False":
            losses_1 += 1

        if v2 == "True":
            wins_2 += 1
        elif v2 == "False":
            losses_2 += 1

        if v1 == "Error" or v2 == "Error":
            failed += 1

        init_val = _try_parse_float(row.get("资金_初始"))
        curr_val = _try_parse_float(row.get("资金_当前"))
        if init_val is not None and funds_initial is None:
            funds_initial = init_val
        if curr_val is not None:
            funds_final = curr_val

    total_valid_1 = wins_1 + losses_1
    total_valid_2 = wins_2 + losses_2
    win_rate_1 = (wins_1 / total_valid_1 * 100.0) if total_valid_1 > 0 else 0.0
    win_rate_2 = (wins_2 / total_valid_2 * 100.0) if total_valid_2 > 0 else 0.0
    funds_pnl = None
    funds_pnl_pct = None
    if funds_initial is not None and funds_final is not None:
        funds_pnl = funds_final - funds_initial
        if funds_initial != 0:
            funds_pnl_pct = funds_pnl / funds_initial * 100.0
    return {
        "wins": wins_2,
        "losses": losses_2,
        "failed": failed,
        "win_rate": win_rate_2,
        "wins_1": wins_1,
        "losses_1": losses_1,
        "win_rate_1": win_rate_1,
        "wins_2": wins_2,
        "losses_2": losses_2,
        "win_rate_2": win_rate_2,
        "funds_initial": funds_initial,
        "funds_final": funds_final,
        "funds_pnl": funds_pnl,
        "funds_pnl_pct": funds_pnl_pct,
    }
