import os
import sys

import streamlit as st

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.dirname(CURRENT_DIR)
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from batch_backtest_app import core, pages, store


def run_app() -> None:
    st.set_page_config(page_title="批量工具", page_icon="📈", layout="wide")

    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            font-size: 18px;
        }
        div[role="radiogroup"] label {
            font-size: 18px;
        }
        div[role="radiogroup"] label > div[role="radio"] {
            border-radius: 999px;
            border: 1px solid #555;
            padding: 4px 12px;
            margin-right: 6px;
        }
        div[role="radiogroup"] label > div[role="radio"] > div:first-child {
            display: none;
        }
        div[role="radiogroup"] label > div[role="radio"][aria-checked="true"] {
            background-color: #1f77b4;
            color: white;
            border-color: #1f77b4;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("📈 批量回测工具")

    core.init_session_state(st.session_state)

    st.sidebar.header("配置")
    cfg = {
        "backend_url": st.sidebar.text_input("后端接口地址", value="http://localhost:8000/api/v1"),
        "analyze_path": st.sidebar.text_input("分析接口路径", value="/analyze/"),
        "concurrency": st.sidebar.number_input("并发数", min_value=1, max_value=20, value=6),
        "task_delay": st.sidebar.number_input(
            "任务启动间隔（秒）",
            min_value=0.0,
            value=1.6,
            help="每个任务启动之间的等待时间，用于缓解后端压力",
        ),
        "timeout": st.sidebar.number_input("超时时间（秒）", min_value=1.0, value=180.0),
        "retries": st.sidebar.number_input("重试次数", min_value=0, value=2),
        "hold_threshold": st.sidebar.number_input("观望阈值", min_value=0.0, value=0.002, format="%.4f"),
    }

    st.sidebar.subheader("默认参数")
    cfg.update(
        {
            "default_kline_count": st.sidebar.number_input("默认K线数量", value=40),
            "default_future_kline_count": st.sidebar.number_input("默认未来K线数量", value=13),
            "default_ai_version": st.sidebar.text_input("默认模型版本", value="original"),
            "default_data_method": st.sidebar.text_input("默认数据方法", value="to_end"),
        }
    )

    pages_list = ["任务来源", "执行回测", "结果"]
    if st.session_state.next_page:
        st.session_state.active_page = st.session_state.next_page
        st.session_state.next_page = None

    active_page = st.radio("导航", pages_list, horizontal=True, key="active_page", label_visibility="collapsed")

    if active_page == "任务来源":
        pages.render_task_source(cfg=cfg, state=st.session_state, store=store, core=core)
    elif active_page == "执行回测":
        pages.render_execute(cfg=cfg, state=st.session_state, store=store, core=core)
    elif active_page == "结果":
        pages.render_results(cfg=cfg, state=st.session_state, core=core)
