
import streamlit as st
import pandas as pd
import os
import re
import sys
import time
import shutil
import random
import uuid
import json
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure we can import batch_backtest from the same directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import batch_backtest
except ImportError:
    st.error("无法导入 batch_backtest.py，请确保它在同一目录下。")
    st.stop()

st.set_page_config(page_title="批量回测工具", page_icon="📈", layout="wide")

st.title("📈 批量回测工具 (Batch Backtest)")

def _normalize_asset_token(token: str) -> str:
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


FAV_ASSETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favorite_assets.json")

def _get_favorites():
    if not os.path.exists(FAV_ASSETS_FILE):
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "DOGEUSDT", "XRPUSDT", "ADAUSDT"]
    try:
        with open(FAV_ASSETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def _save_favorites(assets):
    with open(FAV_ASSETS_FILE, "w", encoding="utf-8") as f:
        json.dump(assets, f, indent=2)


# --- Preset Management ---
PRESETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "task_presets")

def _get_presets_list() -> list[str]:
    if not os.path.exists(PRESETS_DIR):
        return []
    files = [f for f in os.listdir(PRESETS_DIR) if f.endswith(".json")]
    # Sort by modification time desc
    files.sort(key=lambda x: os.path.getmtime(os.path.join(PRESETS_DIR, x)), reverse=True)
    return [f[:-5] for f in files] # remove .json

def _load_preset(name: str) -> list[dict]:
    path = os.path.join(PRESETS_DIR, f"{name}.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"加载预设失败: {e}")
        return []

def _save_preset(name: str, tasks: list[dict]) -> bool:
    if not os.path.exists(PRESETS_DIR):
        os.makedirs(PRESETS_DIR)
    
    # Sanitize name
    safe_name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    if not safe_name:
        return False
        
    path = os.path.join(PRESETS_DIR, f"{safe_name}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2)
        return True
    except Exception as e:
        st.error(f"保存预设失败: {e}")
        return False

def _delete_preset(name: str) -> bool:
    path = os.path.join(PRESETS_DIR, f"{name}.json")
    if os.path.exists(path):
        try:
            os.remove(path)
            return True
        except Exception as e:
            st.error(f"删除预设失败: {e}")
            return False
    return False

def _style_df(df):
    """Apply conditional formatting to the dataframe."""
    def _color_is_correct_col(col):
        colors = []
        for val in col:
            s_val = str(val).upper()
            if s_val == "TRUE":
                colors.append("color: #28a745; font-weight: bold") # Green
            elif s_val == "FALSE":
                colors.append("color: #dc3545; font-weight: bold") # Red
            else:
                colors.append("")
        return colors

    def _color_profit_col(col):
        colors = []
        for val in col:
            s_val = str(val)
            if s_val.startswith("+"):
                colors.append("color: #28a745; font-weight: bold") # Green
            elif s_val.startswith("-"):
                colors.append("color: #dc3545; font-weight: bold") # Red
            else:
                colors.append("")
        return colors

    styler = df.style
    if "is_correct" in df.columns:
        styler = styler.apply(_color_is_correct_col, subset=["is_correct"])
    if "profit_pct_1" in df.columns:
        styler = styler.apply(_color_profit_col, subset=["profit_pct_1"])
    if "profit_pct_2" in df.columns:
        styler = styler.apply(_color_profit_col, subset=["profit_pct_2"])
    return styler

# -------------------------


def _add_favs_callback():
    selected = st.session_state.get("fav_multiselect", [])
    current = st.session_state.get("gen_assets_input", "")
    if selected:
        assets = _parse_assets_input(current)
        for a in selected:
            if a not in assets:
                assets.append(a)
        st.session_state.gen_assets_input = ", ".join(assets)


def _parse_assets_input(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []

    parts = re.split(r"[\s,，、;；\n\r\t]+", text)
    assets: list[str] = []
    seen = set()
    for part in parts:
        normalized = _normalize_asset_token(part)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        assets.append(normalized)
    return assets


def _normalize_assets_input_state() -> None:
    raw = st.session_state.get("gen_assets_input", "")
    assets = _parse_assets_input(raw)
    if assets:
        st.session_state.gen_assets_input = ", ".join(assets)


# Initialize session state
if "tasks" not in st.session_state:
    st.session_state.tasks = []
if "active_page" not in st.session_state:
    st.session_state.active_page = "📁 任务来源 (Task Source)"
if "next_page" not in st.session_state:
    st.session_state.next_page = None
if "bt_last_output_csv" not in st.session_state:
    st.session_state.bt_last_output_csv = ""
if "bt_last_summary" not in st.session_state:
    st.session_state.bt_last_summary = None
if "bt_last_rows" not in st.session_state:
    st.session_state.bt_last_rows = []

# Sidebar Configuration
st.sidebar.header("配置 (Configuration)")

backend_url = st.sidebar.text_input("后端 API 地址", value="http://localhost:8000/api/v1")
analyze_path = st.sidebar.text_input("分析接口路径", value="/analyze/")
concurrency = st.sidebar.number_input("并发数 (Concurrency)", min_value=1, max_value=20, value=6)
task_delay = st.sidebar.number_input("任务启动间隔 (秒)", min_value=0.0, value=1.6, help="每个任务启动之间的等待时间，用于缓解后端压力")
timeout = st.sidebar.number_input("超时时间 (秒)", min_value=1.0, value=180.0)
retries = st.sidebar.number_input("重试次数", min_value=0, value=2)
hold_threshold = st.sidebar.number_input("HOLD 阈值", min_value=0.0, value=0.002, format="%.4f")

st.sidebar.subheader("默认参数 (Defaults)")
default_kline_count = st.sidebar.number_input("默认 K线数量", value=40)
default_future_kline_count = st.sidebar.number_input("默认 未来K线数量", value=13)
default_ai_version = st.sidebar.text_input("默认 AI 版本", value="original")
default_data_method = st.sidebar.text_input("默认 数据方法", value="to_end")

pages = ["📁 任务来源 (Task Source)", "🚀 执行回测 (Execute)", "📊 结果 (Results)"]
if st.session_state.next_page:
    st.session_state.active_page = st.session_state.next_page
    st.session_state.next_page = None
active_page = st.radio("导航", pages, horizontal=True, key="active_page", label_visibility="collapsed")

if active_page == "📁 任务来源 (Task Source)":
    st.markdown("### 选择任务来源")
    source_option = st.radio("模式", ["上传 CSV 文件", "自动生成任务", "📂 加载已保存任务"], horizontal=True)

    if source_option == "上传 CSV 文件":
        st.markdown("#### 方式 1: 直接上传")
        uploaded_file = st.file_uploader("上传任务 CSV 文件", type=["csv"])
        
        st.markdown("#### 方式 2: 从同级目录加载")
        # Detect local CSVs
        current_dir = os.path.dirname(os.path.abspath(__file__))
        local_csvs = [f for f in os.listdir(current_dir) if f.endswith(".csv")]
        
        selected_local_csv = st.selectbox("选择本地 CSV 文件", [""] + local_csvs)
        
        # Determine which source to use
        final_input_path = None
        
        if uploaded_file:
            # Save to temp and read
            temp_path = "temp_tasks_upload.csv"
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            final_input_path = temp_path
            
        elif selected_local_csv:
            final_input_path = os.path.join(current_dir, selected_local_csv)
            
        if final_input_path:
            if st.button("📥 加载选中的文件", type="primary"):
                try:
                    tasks = batch_backtest._read_tasks(final_input_path)
                    st.session_state.tasks = tasks
                    st.session_state.bt_last_output_csv = ""
                    st.session_state.bt_last_summary = None
                    st.session_state.bt_last_rows = []
                    st.success(f"成功加载 {len(tasks)} 个任务 (来源: {selected_local_csv if selected_local_csv else 'Uploaded'})")
                    st.dataframe(pd.DataFrame(tasks).head())
                except Exception as e:
                    st.error(f"解析 CSV 失败: {e}")

    elif source_option == "📂 加载已保存任务":
        st.markdown("#### 加载任务集")
        presets = _get_presets_list()
        if not presets:
            st.info("暂无已保存的任务集。请先在生成或上传任务后保存。")
        else:
            c_load1, c_load2 = st.columns([3, 1])
            selected_preset = c_load1.selectbox("选择任务集", presets, label_visibility="collapsed")
            
            if selected_preset:
                # Preview logic (optional, load to show info)
                pass
            
            col_act1, col_act2 = st.columns(2)
            if col_act1.button("📥 加载选中任务集", type="primary"):
                loaded_tasks = _load_preset(selected_preset)
                if loaded_tasks:
                    st.session_state.tasks = loaded_tasks
                    st.session_state.bt_last_output_csv = ""
                    st.session_state.bt_last_summary = None
                    st.session_state.bt_last_rows = []
                    st.success(f"成功加载任务集: {selected_preset} ({len(loaded_tasks)} 个任务)")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("加载失败或文件为空")

            if col_act2.button("🗑️ 删除该记录"):
                if _delete_preset(selected_preset):
                    st.success(f"已删除: {selected_preset}")
                    time.sleep(1)
                    st.rerun()

    else:
        st.markdown("#### 任务生成器")
        gen_mode = st.selectbox("生成模式", ["完全随机", "周期末端(收盘前5分钟)"])
        
        col_gen1, col_gen2 = st.columns(2)
        with col_gen1:
            if "gen_assets_input" not in st.session_state:
                st.session_state.gen_assets_input = "BTCUSDT, ETHUSDT, SOLUSDT"
            st.text_area(
                "资产列表 (自动规范化，支持中文逗号/英文逗号/大小写/无USDT后缀)",
                key="gen_assets_input",
                on_change=_normalize_assets_input_state,
            )

            # --- 常用币种管理 ---
            fav_list = _get_favorites()
            with st.expander("⭐ 常用币种管理 (Favorites)", expanded=False):
                st.caption("选择常用币种并添加到上方列表")
                
                # Selection for adding
                selected_favs = st.multiselect("选择币种:", fav_list, key="fav_multiselect")
                
                st.button("⬇️ 添加选中到资产列表", on_click=_add_favs_callback)

                st.markdown("---")
                st.caption("编辑常用列表")
                
                # Add
                c_add1, c_add2 = st.columns([3, 1])
                new_fav_txt = c_add1.text_input("新增币种", placeholder="例如 AVAX", key="new_fav_input", label_visibility="collapsed")
                if c_add2.button("添加"):
                    val = st.session_state.new_fav_input
                    norm = _normalize_asset_token(val)
                    if norm:
                        current_favs = _get_favorites()
                        if norm not in current_favs:
                            current_favs.append(norm)
                            _save_favorites(current_favs)
                            st.success(f"已添加 {norm}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.warning(f"{norm} 已存在")
                
                # Delete
                if fav_list:
                    c_del1, c_del2 = st.columns([3, 1])
                    del_fav_val = c_del1.selectbox("删除币种", fav_list, key="del_fav_select", label_visibility="collapsed")
                    if c_del2.button("删除"):
                        if del_fav_val:
                            current_favs = _get_favorites()
                            if del_fav_val in current_favs:
                                current_favs.remove(del_fav_val)
                                _save_favorites(current_favs)
                                st.success(f"已删除 {del_fav_val}")
                                time.sleep(0.5)
                                st.rerun()
            # -------------------

            gen_assets = st.session_state.gen_assets_input
            gen_timeframe = st.selectbox("时间周期", ["15m", "1h", "4h", "1d"], index=1)
            
            if gen_mode == "完全随机":
                gen_count = st.number_input("生成数量 (每个资产)", min_value=1, value=10)
            else:
                gen_count = st.number_input("生成数量 (每个资产, 随机抽取)", min_value=1, value=10)
                st.info(f"将按日期顺序生成所有符合条件的 {gen_timeframe} 周期末端时间点，然后随机抽取 {gen_count} 个。")
        
        with col_gen2:
            gen_start_date = st.date_input("开始日期", value=datetime.now() - timedelta(days=365))
            gen_end_date = st.date_input("结束日期", value=datetime.now() - timedelta(days=1))
            
        if st.button("生成任务", type="secondary"):
            assets = _parse_assets_input(gen_assets)
            if not assets:
                st.error("请至少输入一个有效资产")
            else:
                generated_tasks = []
                start_dt = datetime.combine(gen_start_date, datetime.min.time())
                end_dt = datetime.combine(gen_end_date, datetime.max.time())
                
                if end_dt <= start_dt:
                    st.error("结束日期必须晚于开始日期")
                else:
                    for asset in assets:
                        if gen_mode == "完全随机":
                            start_ts = int(start_dt.timestamp())
                            end_ts = int(end_dt.timestamp())
                            for _ in range(gen_count):
                                random_ts = random.randint(start_ts, end_ts)
                                dt = datetime.fromtimestamp(random_ts)
                                task = {
                                    "task_id": f"gen_{uuid.uuid4().hex[:8]}",
                                    "asset": asset,
                                    "timeframe": gen_timeframe,
                                    "end_date": dt.strftime("%Y-%m-%d"),
                                    "end_time": dt.strftime("%H:%M"),
                                    "kline_count": default_kline_count,
                                    "future_kline_count": default_future_kline_count,
                                    "ai_version": default_ai_version,
                                    "data_method": default_data_method
                                }
                                generated_tasks.append(task)
                        
                        else: # 周期末端模式
                            # Determine cycle offsets based on timeframe
                            cycle_offsets = []
                            if gen_timeframe == "4h":
                                cycle_offsets = [4, 8, 12, 16, 20, 24]
                            elif gen_timeframe == "1h":
                                cycle_offsets = list(range(1, 25)) # 1, 2, ..., 24
                            else:
                                st.error(f"周期末端模式暂不支持 {gen_timeframe}，仅支持 1h 和 4h")
                                break

                            # 1. Generate ALL possible candidates first
                            candidates = []
                            iter_day = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
                            end_day_limit = end_dt
                            
                            while iter_day < end_day_limit:
                                for offset in cycle_offsets:
                                    cycle_end_dt = iter_day + timedelta(hours=offset)
                                    
                                    # Check bounds
                                    if cycle_end_dt <= start_dt:
                                        continue
                                    if cycle_end_dt > end_dt:
                                        break
                                    
                                    # Generate time window: [cycle_end - 5min, cycle_end)
                                    window_start = cycle_end_dt - timedelta(minutes=5)
                                    
                                    rand_min = random.randint(0, 4)
                                    final_dt = window_start + timedelta(minutes=rand_min)
                                    candidates.append(final_dt)
                                
                                iter_day += timedelta(days=1)
                            
                            # 2. Randomly sample from candidates
                            if not candidates:
                                st.warning(f"资产 {asset}: 在指定日期范围内没有找到符合条件的周期末端时间点。")
                                continue
                                
                            if len(candidates) <= gen_count:
                                selected_dts = candidates
                            else:
                                selected_dts = random.sample(candidates, gen_count)
                            
                            # 3. Create tasks
                            for dt in selected_dts:
                                task = {
                                    "task_id": f"end_{gen_timeframe}_{dt.strftime('%Y%m%d%H%M')}_{uuid.uuid4().hex[:4]}",
                                    "asset": asset,
                                    "timeframe": gen_timeframe,
                                    "end_date": dt.strftime("%Y-%m-%d"),
                                    "end_time": dt.strftime("%H:%M"),
                                    "kline_count": default_kline_count,
                                    "future_kline_count": default_future_kline_count,
                                    "ai_version": default_ai_version,
                                    "data_method": default_data_method
                                }
                                generated_tasks.append(task)

                    if generated_tasks:
                        st.session_state.tasks = generated_tasks
                        st.session_state.bt_last_output_csv = ""
                        st.session_state.bt_last_summary = None
                        st.session_state.bt_last_rows = []
                        st.success(f"成功生成 {len(generated_tasks)} 个任务")
                        st.dataframe(pd.DataFrame(generated_tasks).head())

    # Preview Current Tasks
    if st.session_state.tasks:
        st.markdown("---")
        st.markdown(f"#### 当前待执行任务: {len(st.session_state.tasks)} 个")
        
        # Save Preset UI
        with st.expander("💾 保存当前任务集 (Save Preset)", expanded=False):
            c_save1, c_save2 = st.columns([3, 1])
            preset_name = c_save1.text_input("任务集名称", placeholder="例如: BTC_4H_2024", label_visibility="collapsed")
            if c_save2.button("保存"):
                if preset_name:
                    if _save_preset(preset_name, st.session_state.tasks):
                        st.success(f"已保存: {preset_name}")
                else:
                    st.warning("请输入名称")

        with st.expander("查看所有任务详情"):
            st.dataframe(pd.DataFrame(st.session_state.tasks))

elif active_page == "🚀 执行回测 (Execute)":
    st.markdown("### 执行回测")
    
    col_run1, col_run2 = st.columns(2)
    with col_run1:
        output_path = st.text_input("结果输出路径 (服务器/本地路径)", value=os.path.join("tools", "backtest_results.csv"))
    with col_run2:
        rerun = st.checkbox("强制重跑 (不跳过已存在结果)", value=False)

    if st.button("开始回测 (Start Backtest)", type="primary"):
        st.warning("⚠️ 警告：回测运行期间请勿切换左侧菜单页面，否则会导致进度视图丢失！")
        if not st.session_state.tasks:
            st.error("当前没有任务，请先在 '任务来源' 标签页上传或生成任务！")
        else:
            tasks = st.session_state.tasks
            
            # Prepare arguments
            base_url = batch_backtest._normalize_base_url(backend_url)
            if not analyze_path.startswith("/"):
                analyze_path = "/" + analyze_path
                
            defaults = {
                "asset": "",
                "timeframe": "",
                "end_date": "",
                "end_time": "",
                "kline_count": default_kline_count,
                "future_kline_count": default_future_kline_count,
                "ai_version": default_ai_version,
                "data_method": default_data_method,
            }
            
            # Initialize output file
            fieldnames = [
                "task_id", "asset", "timeframe", "end_date", "end_time",
                "分析时的价格", "未来第一根K线的价格", "未来第二根K线的价格",
                "ai_decision", "is_correct", "profit_pct_1", "profit_pct_2", "cumulative_win_rate",
                "duration_s", "result_id", "ai_version",
                "data_method", "kline_count", "future_kline_count", "error"
            ]
            
            output_csv = os.path.abspath(output_path)
            st.session_state.bt_last_output_csv = output_csv
            st.session_state.bt_last_summary = None
            st.session_state.bt_last_rows = []
            
            # Handle existing file logic
            existing_keys = set()
            if not rerun:
                existing_header, existing_keys = batch_backtest._load_existing_keys(output_csv)
                if existing_header and existing_header != fieldnames:
                    st.warning(f"检测到输出CSV表头已变更，正在原地迁移：{output_csv}")
                    batch_backtest._migrate_output_csv_in_place(output_csv, fieldnames)
                    _, existing_keys = batch_backtest._load_existing_keys(output_csv)
            
            batch_backtest._ensure_output_header(output_csv, fieldnames)
            
            # Filter tasks
            to_run = []
            skipped_count = 0
            if rerun:
                to_run = tasks
            else:
                for row in tasks:
                    try:
                        key = batch_backtest._task_key_from_row(row, defaults)
                        if key in existing_keys:
                            skipped_count += 1
                            continue
                        to_run.append(row)
                    except Exception:
                        to_run.append(row)

            st.info(f"任务总数: {len(tasks)} | 将执行: {len(to_run)} | 跳过: {skipped_count}")
            
            if not to_run:
                st.success("所有任务已完成，无需执行！")
                st.session_state.bt_last_summary = {
                    "total_tasks": len(tasks),
                    "run_tasks": 0,
                    "skipped_tasks": skipped_count,
                    "failed": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0.0,
                    "total_duration_s": 0.0,
                }
                st.session_state.next_page = "📊 结果 (Results)"
                st.rerun()
            else:
                # Execution Loop
                progress_bar = st.progress(0)
                status_text = st.empty()
                metrics_placeholder = st.empty()
                result_table = st.empty()
                
                completed = 0
                failed = 0
                stats_wins = 0
                stats_losses = 0
                
                start_time = time.time()
                
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = []
                    for i, row in enumerate(to_run):
                        # 提交任务
                        fut = executor.submit(
                            batch_backtest._run_one_task,
                            base_url,
                            analyze_path,
                            timeout,
                            int(retries),
                            1.0, # backoff
                            hold_threshold,
                            row,
                            defaults,
                        )
                        futures.append(fut)
                        
                        # 延迟启动（除了最后一个任务）
                        if i < len(to_run) - 1 and task_delay > 0:
                            time.sleep(task_delay)
                    
                    for i, fut in enumerate(as_completed(futures)):
                        result_row = fut.result()
                        
                        # Update stats
                        is_correct = result_row.get("is_correct")
                        if is_correct == "True":
                            stats_wins += 1
                        elif is_correct == "False":
                            stats_losses += 1
                        
                        total_valid = stats_wins + stats_losses
                        win_rate = (stats_wins / total_valid * 100.0) if total_valid > 0 else 0.0
                        result_row["cumulative_win_rate"] = f"{win_rate:.2f}%" if total_valid > 0 else "N/A"
                        
                        if result_row.get("is_correct") == "Error":
                            failed += 1
                        
                        # Write to file
                        try:
                            batch_backtest._append_output_row(output_csv, fieldnames, result_row)
                        except PermissionError:
                            st.error(f"❌ 写入失败！请立即关闭文件: {output_csv} (已重试多次)")
                            # Don't raise, just let it continue (though data might be lost for this row in CSV, but present in UI)
                        except Exception as e:
                            st.error(f"❌ 写入 CSV 出错: {e}")
                        
                        completed += 1
                        progress = completed / len(to_run)
                        progress_bar.progress(progress)
                        
                        elapsed = time.time() - start_time
                        avg_time = elapsed / completed if completed > 0 else 0
                        eta = avg_time * (len(to_run) - completed)
                        
                        status_text.text(f"正在处理: {result_row.get('task_id', 'Unknown')} | ETA: {eta:.1f}s")
                        
                        # Update metrics
                        col_m1, col_m2, col_m3, col_m4 = metrics_placeholder.columns(4)
                        col_m1.metric("已完成", f"{completed}/{len(to_run)}")
                        col_m2.metric("胜场", stats_wins)
                        col_m3.metric("负场", stats_losses)
                        col_m4.metric("当前胜率", f"{win_rate:.2f}%")
                        
                        # Update table (show last 10)
                        st.session_state.bt_last_rows.append(result_row)
                        if len(st.session_state.bt_last_rows) > 200:
                            st.session_state.bt_last_rows = st.session_state.bt_last_rows[-200:]
                        df = pd.DataFrame(st.session_state.bt_last_rows[-10:])
                        # Select important columns for display
                        display_cols = ["task_id", "asset", "end_date", "end_time", "ai_decision", "is_correct", "profit_percentage", "cumulative_win_rate"]
                        # filter cols that exist
                        display_cols = [c for c in display_cols if c in df.columns]
                        result_table.dataframe(_style_df(df[display_cols]), use_container_width=True)

                st.success("回测完成！")
                st.balloons()
                
                # Show final results summary
                total_valid = stats_wins + stats_losses
                final_win_rate = (stats_wins / total_valid * 100.0) if total_valid > 0 else 0.0
                total_duration_s = round(time.time() - start_time, 3)
                st.session_state.bt_last_summary = {
                    "total_tasks": len(tasks),
                    "run_tasks": completed,
                    "skipped_tasks": skipped_count,
                    "failed": failed,
                    "wins": stats_wins,
                    "losses": stats_losses,
                    "win_rate": final_win_rate,
                    "total_duration_s": total_duration_s,
                }
                st.session_state.next_page = "📊 结果 (Results)"
                st.rerun()
                st.markdown(f"""
                ### 最终统计
                - **总任务**: {len(tasks)}
                - **本次运行**: {completed}
                - **失败**: {failed}
                - **胜率**: {final_win_rate:.2f}% ({stats_wins} 胜 / {stats_losses} 负)
                """)
                
                # Download button for the result file
                if os.path.exists(output_csv):
                    with open(output_csv, "rb") as f:
                        st.download_button(
                            label="下载结果 CSV",
                            data=f,
                            file_name="backtest_results.csv",
                            mime="text/csv"
                        )

else:
    st.markdown("### 最近一次运行结果")
    
    # Reload Section
    with st.expander("📂 加载历史结果", expanded=True):
        c_res1, c_res2 = st.columns([3, 1])
        default_path = st.session_state.bt_last_output_csv or os.path.join("tools", "backtest_results.csv")
        load_path = c_res1.text_input("结果文件路径", value=default_path)
        if c_res2.button("🔄 加载/刷新结果"):
            if os.path.exists(load_path):
                try:
                    df = pd.read_csv(load_path)
                    st.session_state.bt_last_output_csv = load_path
                    st.session_state.bt_last_rows = df.to_dict("records")
                    
                    # Calculate summary
                    total = len(df)
                    wins = len(df[df["is_correct"] == True])
                    losses = len(df[df["is_correct"] == False])
                    errors = len(df[df["is_correct"] == "Error"])
                    valid = wins + losses
                    rate = (wins / valid * 100) if valid > 0 else 0
                    
                    st.session_state.bt_last_summary = {
                        "total_tasks": "Unknown",
                        "run_tasks": total,
                        "skipped_tasks": "Unknown",
                        "failed": errors,
                        "wins": wins,
                        "losses": losses,
                        "win_rate": rate,
                        "total_duration_s": 0.0,
                    }
                    st.success(f"成功加载 {total} 条记录")
                    st.rerun()
                except Exception as e:
                    st.error(f"读取失败: {e}")
            else:
                st.error("文件不存在")

    summary = st.session_state.bt_last_summary
    output_csv = st.session_state.bt_last_output_csv
    
    if not summary and not output_csv:
        st.info("暂无结果。请先在“执行回测”运行一次。")
    else:
        col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)
        col_r1.metric("本次运行", summary.get("run_tasks") if summary else "N/A")
        col_r2.metric("跳过", summary.get("skipped_tasks") if summary else "N/A")
        col_r3.metric("失败", summary.get("failed") if summary else "N/A")
        col_r4.metric("胜率", f"{summary.get('win_rate', 0.0):.2f}%" if summary else "N/A")
        if summary:
            col_r5.metric("总耗时", f"{summary.get('total_duration_s', 0.0):.1f}s")
        else:
            col_r5.metric("总耗时", "N/A")

        if st.session_state.bt_last_rows:
            df = pd.DataFrame(st.session_state.bt_last_rows)
            display_cols = ["task_id", "asset", "end_date", "end_time", "ai_decision", "is_correct", "profit_pct_1", "profit_pct_2", "cumulative_win_rate"]
            display_cols = [c for c in display_cols if c in df.columns]
            if display_cols:
                st.dataframe(_style_df(df[display_cols]), use_container_width=True)
            else:
                st.dataframe(_style_df(df), use_container_width=True)

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if output_csv and os.path.exists(output_csv):
                with open(output_csv, "rb") as f:
                    st.download_button(
                        label="下载结果 CSV",
                        data=f,
                        file_name=os.path.basename(output_csv),
                        mime="text/csv",
                    )
        with col_b2:
            if st.button("清空结果显示", type="secondary"):
                st.session_state.bt_last_output_csv = ""
                st.session_state.bt_last_summary = None
                st.session_state.bt_last_rows = []
