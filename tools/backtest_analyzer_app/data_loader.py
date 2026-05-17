"""
回测分析工具 — 数据加载模块。

功能：
- 递归扫描 tools/ 目录下的 .csv 文件
- 解析回测 CSV（过滤分隔行、转换数值列、多编码支持）
- 安全读取列（缺失时返回默认类型空 Series）
"""

import os
from typing import List, Optional

import pandas as pd
import streamlit as st


# ── 路径工具 ──────────────────────────────────────────────────────────

def _tools_dir() -> str:
    """返回 tools/ 目录的绝对路径。"""
    current = os.path.dirname(os.path.abspath(__file__))  # backtest_analyzer_app/
    return os.path.dirname(current)  # tools/


# ── 辅助函数 ──────────────────────────────────────────────────────────

def _is_numeric_or_empty(val: object) -> bool:
    """判断值是否为数字（或可转为数字）或为空/NaN。

    用于过滤 CSV 中的分隔行（如 "=== 新批次开始 ...===" 所在行）。
    """
    if val is None:
        return True
    if isinstance(val, float) and pd.isna(val):
        return True
    s = str(val).strip()
    if s == "":
        return True
    if s.startswith("==="):
        return False
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


# ── 公共 API ──────────────────────────────────────────────────────────

def load_csv_files() -> List[str]:
    """递归扫描 tools/ 目录，返回所有 .csv 文件的绝对路径列表。

    返回按路径名排序的列表。
    """
    tools_dir = _tools_dir()
    csv_files: List[str] = []
    for root, _dirs, files in os.walk(tools_dir):
        for f in files:
            if f.lower().endswith(".csv"):
                csv_files.append(os.path.join(root, f))
    csv_files.sort()
    return csv_files


def safe_col(df: pd.DataFrame, col_name: str, default_dtype: type = float):
    """安全获取 DataFrame 列。

    如果列存在则返回该列，否则返回全为默认值的空 Series（保持索引一致）。

    Args:
        df: 目标 DataFrame。
        col_name: 列名。
        default_dtype: 缺失时返回 Series 的数据类型（默认 float，返回全 NaN）。

    Returns:
        pd.Series — 原始列或默认空列。
    """
    if col_name in df.columns:
        return df[col_name]
    return pd.Series(dtype=default_dtype, index=df.index)


@st.cache_data(show_spinner="正在加载 CSV 文件…")
def parse_backtest_csv(filepath: str) -> Optional[pd.DataFrame]:
    """读取并清洗回测 CSV 文件。

    处理流程：
    1. 多编码尝试（utf-8 → gbk → latin-1）
    2. 过滤非数据行（task_id 非数字/空 → 丢弃）
    3. 数值列强制转换为 float
    4. 布尔列转换
    5. 日期/时间列标准化

    Args:
        filepath: CSV 文件的绝对路径。

    Returns:
        清洗后的 DataFrame；如果文件不存在或无法解析则返回 None。
    """
    if not filepath or not os.path.exists(filepath):
        st.error(f"文件不存在: {filepath}")
        return None

    # ── 1. 多编码读取 ──────────────────────────────────────────────
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin-1"]
    df = None
    last_error: Optional[Exception] = None

    for enc in encodings:
        try:
            df = pd.read_csv(filepath, encoding=enc)
            last_error = None
            break
        except (UnicodeDecodeError, UnicodeError) as e:
            last_error = e
            continue
        except Exception as e:
            last_error = e
            continue

    if df is None or df.empty:
        detail = str(last_error) if last_error else "文件为空"
        st.error(f"无法读取 CSV: {filepath}\n{detail}")
        return None

    # ── 2. 过滤分隔行 ──────────────────────────────────────────────
    if "task_id" in df.columns:
        mask = df["task_id"].apply(_is_numeric_or_empty)
    else:
        # 无 task_id 列时尝试用第一列过滤
        first_col = df.columns[0]
        mask = df[first_col].apply(_is_numeric_or_empty)

    df = df.loc[mask].copy()

    if df.empty:
        st.warning("CSV 中无有效数据行（所有行均被过滤）")
        return df

    # ── 3. 百分比列清洗（去除 % 符号再转数值） ─────────────────────
    pct_cols_to_clean = [
        "profit_pct_1",
        "profit_pct_2",
        "本次盈亏百分比",
        "cumulative_win_rate",
        "cumulative_win_rate_1",
        "cumulative_win_rate_2",
    ]
    for col in pct_cols_to_clean:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace("%", "").str.strip(),
                errors="coerce",
            )

    # ── 4. 通用数值列转换 ──────────────────────────────────────────
    numeric_cols = [
        "task_id",
        "profit_pct_1",
        "profit_pct_2",
        "cumulative_win_rate",
        "cumulative_win_rate_1",
        "cumulative_win_rate_2",
        "duration_s",
        "kline_count",
        "future_kline_count",
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
        "本次盈亏",
        "本次盈亏百分比",
        "逆势_偏离次数",
        "逆势_最大偏离%",
        "fusion_score",
        "fusion_confidence",
        "indicator_score",
        "structure_score",
        "mechanics_score",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── 5. 布尔列转换 ──────────────────────────────────────────────
    bool_cols = ["is_correct", "is_correct_1", "is_correct_2"]
    for col in bool_cols:
        if col in df.columns:
            # 处理字符串 "True"/"False" 和 Python bool
            df[col] = df[col].apply(
                lambda x: (
                    True
                    if str(x).strip().lower() == "true"
                    else False
                    if str(x).strip().lower() == "false"
                    else pd.NA
                )
            )

    # ── 6. 字符串列标准化 ──────────────────────────────────────────
    str_cols = [
        "end_time",
        "asset",
        "timeframe",
        "ai_decision",
        "ai_version",
        "data_method",
        "result_id",
        "AGENT_MODEL",
        "GRAPH_MODEL",
        "回测模式",
    ]
    for col in str_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace({"nan": pd.NA, "": pd.NA, "None": pd.NA})

    # ── 7. 日期列解析 ──────────────────────────────────────────────
    if "end_date" in df.columns:
        df["end_date"] = pd.to_datetime(df["end_date"], errors="coerce")

    return df
