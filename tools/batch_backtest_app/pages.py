import os
import random
import time
import uuid
import subprocess
import platform
import signal
from datetime import datetime, timedelta
from typing import Any, MutableMapping, Optional

import pandas as pd
import streamlit as st

from batch_backtest_app import core, engine, store


def render_task_source(
    *,
    cfg: dict[str, Any],
    state: MutableMapping[str, Any],
    store: Any,
    core: Any,
) -> None:
    st.markdown("### 选择任务来源")
    source_option = st.radio("模式", ["上传任务文件", "自动生成任务", "加载已保存任务"], horizontal=True)

    if source_option == "上传任务文件":
        st.markdown("#### 方式 1: 直接上传")
        uploaded_file = st.file_uploader("上传任务文件", type=["csv"])

        st.markdown("#### 方式 2: 从同级目录加载")
        tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        local_csvs = [f for f in os.listdir(tools_dir) if f.endswith(".csv")]
        selected_local_csv = st.selectbox("选择本地任务文件", [""] + local_csvs)

        final_input_path = None
        selected_source_name = ""
        if uploaded_file:
            temp_path = os.path.join(tools_dir, "temp_tasks_upload.csv")
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            final_input_path = temp_path
            selected_source_name = "上传文件"
        elif selected_local_csv:
            final_input_path = os.path.join(tools_dir, selected_local_csv)
            selected_source_name = selected_local_csv

        if final_input_path:
            if st.button("加载选中的文件", type="primary"):
                try:
                    tasks = engine.read_tasks(final_input_path)
                    state["tasks"] = tasks
                    state["bt_last_output_csv"] = ""
                    state["bt_last_summary"] = None
                    state["bt_last_rows"] = []
                    st.success(f"成功加载 {len(tasks)} 个任务（来源：{selected_source_name}）")
                    st.dataframe(pd.DataFrame(tasks).head())
                except Exception as e:
                    st.error(f"解析失败：{e}")

    elif source_option == "📂 加载已保存任务":
        st.markdown("#### 加载任务集")
        presets = store.get_presets_list()
        if not presets:
            st.info("暂无已保存的任务集。请先在生成或上传任务后保存。")
        else:
            c_load1, _c_load2 = st.columns([3, 1])
            selected_preset = c_load1.selectbox("选择任务集", presets, label_visibility="collapsed")

            col_act1, col_act2 = st.columns(2)
            if col_act1.button("加载选中任务集", type="primary"):
                try:
                    loaded_tasks = store.load_preset(selected_preset)
                    if loaded_tasks:
                        state["tasks"] = loaded_tasks
                        state["bt_last_output_csv"] = ""
                        state["bt_last_summary"] = None
                        state["bt_last_rows"] = []
                        st.success(f"成功加载任务集: {selected_preset} ({len(loaded_tasks)} 个任务)")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("加载失败或文件为空")
                except Exception as e:
                    st.error(f"加载失败: {e}")

            if col_act2.button("删除该记录"):
                try:
                    store.delete_preset(selected_preset)
                    st.success(f"已删除: {selected_preset}")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"删除预设失败: {e}")

    else:
        st.markdown("#### 任务生成器")
        gen_mode = st.selectbox("生成模式", ["完全随机", "周期末端(收盘前5分钟)"])

        col_gen1, col_gen2 = st.columns(2)
        with col_gen1:
            st.text_area(
                "资产列表 (自动规范化，支持中文逗号/英文逗号/大小写/无USDT后缀)",
                key="gen_assets_input",
                on_change=lambda: _normalize_assets_input_state(state),
            )

            fav_list = store.get_favorites()
            with st.expander("常用币种管理", expanded=False):
                st.caption("选择常用币种并添加到上方列表")
                selected_favs = st.multiselect("选择币种:", fav_list, key="fav_multiselect")
                st.button("添加选中到资产列表", on_click=lambda: _add_favs_callback(state, selected_favs))

                st.markdown("---")
                st.caption("编辑常用列表")
                c_add1, c_add2 = st.columns([3, 1])
                c_add1.text_input("新增币种", placeholder="例如 AVAX", key="new_fav_input", label_visibility="collapsed")
                if c_add2.button("添加"):
                    norm = core.normalize_asset_token(state.get("new_fav_input", ""))
                    if norm:
                        current_favs = store.get_favorites()
                        if norm not in current_favs:
                            current_favs.append(norm)
                            store.save_favorites(current_favs)
                            st.success(f"已添加 {norm}")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.warning(f"{norm} 已存在")

                if fav_list:
                    c_del1, c_del2 = st.columns([3, 1])
                    del_fav_val = c_del1.selectbox("删除币种", fav_list, key="del_fav_select", label_visibility="collapsed")
                    if c_del2.button("删除"):
                        if del_fav_val:
                            current_favs = store.get_favorites()
                            if del_fav_val in current_favs:
                                current_favs.remove(del_fav_val)
                                store.save_favorites(current_favs)
                                st.success(f"已删除 {del_fav_val}")
                                time.sleep(0.5)
                                st.rerun()

            
            st.markdown("##### 时间周期设置")
            gen_tf_mode = st.radio("周期模式", ["常用预设", "自定义/多周期"], horizontal=True, label_visibility="collapsed", key="gen_tf_mode_radio")
            
            if gen_tf_mode == "常用预设":
                gen_timeframe = st.selectbox("选择周期", ["15m", "1h", "4h", "1d"], index=1, label_visibility="collapsed")
            else:
                gen_timeframe = st.text_input("输入周期", value="4h+15m", help="支持多周期（如 4h+15m），如果是周期末端模式，首个周期必须是 1h 或 4h")

            gen_count = st.number_input("生成数量 (每个资产)", min_value=1, value=10)
            if gen_mode != "完全随机":
                st.info(f"将按日期顺序生成所有符合条件的 {gen_timeframe} 周期末端时间点，然后随机抽取 {gen_count} 个。")

        with col_gen2:
            gen_start_date = st.date_input("开始日期", value=datetime.now() - timedelta(days=365))
            gen_end_date = st.date_input("结束日期", value=datetime.now() - timedelta(days=1))

        if st.button("生成任务", type="secondary"):
            assets = core.parse_assets_input(state.get("gen_assets_input", ""))
            if not assets:
                st.error("请至少输入一个有效资产")
            else:
                start_dt = datetime.combine(gen_start_date, datetime.min.time())
                end_dt = datetime.combine(gen_end_date, datetime.max.time())
                if end_dt <= start_dt:
                    st.error("结束日期必须晚于开始日期")
                else:
                    uuid_factory = lambda: uuid.uuid4().hex[:8]
                    if gen_mode == "完全随机":
                        tasks = core.generate_tasks_random(
                            assets,
                            gen_timeframe,
                            int(gen_count),
                            start_dt,
                            end_dt,
                            default_kline_count=int(cfg["default_kline_count"]),
                            default_future_kline_count=int(cfg["default_future_kline_count"]),
                            default_ai_version=str(cfg["default_ai_version"]),
                            default_data_method=str(cfg["default_data_method"]),
                            uuid_factory=uuid_factory,
                            rand_int=random.randint,
                        )
                    else:
                        tasks, errs = core.generate_tasks_cycle_end(
                            assets,
                            gen_timeframe,
                            int(gen_count),
                            start_dt,
                            end_dt,
                            default_kline_count=int(cfg["default_kline_count"]),
                            default_future_kline_count=int(cfg["default_future_kline_count"]),
                            default_ai_version=str(cfg["default_ai_version"]),
                            default_data_method=str(cfg["default_data_method"]),
                            uuid_factory=lambda: uuid.uuid4().hex,
                            rand_sample=random.sample,
                            rand_int=random.randint,
                        )
                        for msg in errs:
                            st.error(msg)
                    if tasks:
                        state["tasks"] = tasks
                        state["bt_last_output_csv"] = ""
                        state["bt_last_summary"] = None
                        state["bt_last_rows"] = []
                        st.success(f"成功生成 {len(tasks)} 个任务")
                        st.dataframe(pd.DataFrame(tasks).head())

    if state.get("tasks"):
        st.markdown("---")
        st.markdown(f"#### 当前待执行任务：{len(state['tasks'])} 个")

        with st.expander("💾 保存当前任务集", expanded=False):
            c_save1, c_save2 = st.columns([3, 1])
            preset_name = c_save1.text_input("任务集名称", placeholder="例如: BTC_4H_2024", label_visibility="collapsed")
            if c_save2.button("保存"):
                if preset_name:
                    try:
                        ok, safe_name = store.save_preset(preset_name, state["tasks"])
                        if ok:
                            st.success(f"已保存: {safe_name}")
                    except Exception as e:
                        st.error(f"保存预设失败: {e}")
                else:
                    st.warning("请输入名称")

        with st.expander("查看所有任务详情"):
            st.dataframe(pd.DataFrame(state["tasks"]))


def render_execute(
    *,
    cfg: dict[str, Any],
    state: MutableMapping[str, Any],
    store: Any,
    core: Any,
) -> None:
    st.markdown("### 执行回测")

    # --- 后台任务监控 ---
    daemon_status = store.load_daemon_status()
    is_daemon_running = False
    if daemon_status and "pid" in daemon_status:
        try:
            pid = daemon_status["pid"]
            is_windows = platform.system() == "Windows"
            
            if is_windows:
                # Check if process exists (Windows compatible tasklist check)
                output = subprocess.check_output(f'tasklist /fi "PID eq {pid}"', shell=True).decode('gbk', errors='ignore')
                if str(pid) in output:
                    is_daemon_running = True
            else:
                # Linux/Unix check using ps
                try:
                    os.kill(pid, 0) # Check if signal can be sent
                    is_daemon_running = True
                except OSError:
                    is_daemon_running = False

            if not is_daemon_running:
                 # Cleanup stale status if confirmed dead
                if os.path.exists(store.DAEMON_STATUS_FILE):
                    os.remove(store.DAEMON_STATUS_FILE)
                    
        except Exception:
            # Fallback: assume running if status file is very recent (< 30s)
            last_hb = daemon_status.get("last_heartbeat")
            if last_hb:
                try:
                    dt = datetime.fromisoformat(last_hb)
                    if (datetime.now() - dt).total_seconds() < 30:
                        is_daemon_running = True
                except:
                    pass

    if is_daemon_running:
        st.info(f"🚀 后台任务正在运行中 (PID: {daemon_status['pid']})")
        
        progress = store.load_daemon_progress()
        if progress and progress.get("is_running"):
            total = progress.get("total_tasks", 1)
            completed = progress.get("completed_count", 0)
            
            p_val = completed / total if total > 0 else 0.0
            st.progress(p_val)
            st.caption(f"进度: {completed}/{total} | 状态: {progress.get('status', '未知')}")
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("胜场 (Wins)", progress.get("stats_wins", 0))
            m2.metric("负场 (Losses)", progress.get("stats_losses", 0))
            m3.metric("失败 (Failed)", progress.get("failed_count", 0))
            
            equity = progress.get("equity")
            if equity is not None:
                m4.metric("当前资金", f"{float(equity):.2f}")
            else:
                m4.metric("当前资金", "N/A")
            
            last_update = progress.get("last_update", "")
            if last_update:
                try:
                    t_str = last_update.split('T')[-1][:8]
                    m5.metric("更新时间", t_str)
                except:
                    m5.metric("更新时间", "刚刚")

            # Detail expander
            with st.expander("当前任务详情", expanded=True):
                st.write(f"Task ID: {progress.get('current_task_id')}")
                st.write(f"Asset: {progress.get('current_asset')} ({progress.get('current_timeframe')})")
                st.write(f"End Date: {progress.get('current_end_date')} {progress.get('current_end_time')}")

            col_mon1, col_mon2 = st.columns(2)
            if col_mon1.button("🛑 停止后台任务", type="primary"):
                try:
                    if platform.system() == "Windows":
                        subprocess.call(f"taskkill /F /PID {daemon_status['pid']}", shell=True)
                    else:
                        os.kill(daemon_status['pid'], signal.SIGTERM)
                        
                    st.success("已发送停止信号")
                    if os.path.exists(store.DAEMON_STATUS_FILE):
                        os.remove(store.DAEMON_STATUS_FILE)
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"停止失败: {e}")
                    
            if col_mon2.button("🔄 刷新状态"):
                st.rerun()
                
            # Auto refresh
            time.sleep(3)
            st.rerun()
        else:
            st.warning("正在等待后台进程启动或初始化...")
            if st.button("刷新"):
                st.rerun()
            time.sleep(2)
            st.rerun()
            
        return

    # --- 配置面板 (仅当无后台任务时显示) ---
    col_run1, col_run2 = st.columns(2)
    with col_run1:
        output_path = st.text_input("结果输出路径", value=os.path.join("tools", "backtest_results.csv"))
    with col_run2:
        rerun = st.checkbox("强制重跑", value=False)

    backtest_mode = st.radio("回测模式", ["普通回测", "带资金回测"], horizontal=True)

    funds_cfg: Optional[dict[str, Any]] = None
    if backtest_mode == "带资金回测":
        with st.expander("资金回测参数", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                initial_equity = st.number_input("初始资金", min_value=1.0, value=10000.0, step=100.0)
                position_mode = st.selectbox(
                    "仓位管理策略",
                    options=["固定百分比", "固定金额", "阶梯仓位"],
                    index=0,
                    help="固定百分比：每次使用资金的一定比例；固定金额：每次使用固定USDT金额；阶梯仓位：盈利保护策略，保守阶段用固定比例，激进阶段只用盈利部分"
                )

                # 阶梯仓位策略的额外参数
                conservative_base_ratio = 30.0
                aggressive_threshold_pct = 150.0
                conservative_threshold_pct = 110.0
                use_aggressive_mode_only_profit = True

                if position_mode == "固定百分比":
                    allocation_pct = st.number_input("仓位比例（百分比）", min_value=0.0, max_value=100.0, value=100.0, step=1.0)
                    fixed_amount = 1000.0
                elif position_mode == "固定金额":
                    fixed_amount = st.number_input("固定开仓金额（USDT）", min_value=0.0, value=1000.0, step=100.0)
                    allocation_pct = 100.0
                else:  # 阶梯仓位
                    st.markdown("##### 保守阶段参数")
                    conservative_base_ratio = st.number_input(
                        "保守基础比例（%）", min_value=0.0, max_value=100.0, value=30.0, step=5.0,
                        help="保守模式下使用的资金比例"
                    )

                    st.markdown("##### 阶梯切换阈值")
                    aggressive_threshold_pct = st.number_input(
                        "激进阈值（%）", min_value=100.0, max_value=500.0, value=150.0, step=10.0,
                        help="资金达到初始本金的此百分比时进入激进模式"
                    )
                    conservative_threshold_pct = st.number_input(
                        "保守阈值（%）", min_value=100.0, max_value=200.0, value=110.0, step=5.0,
                        help="激进模式下，资金跌破此百分比时回到保守模式（滞后切换）"
                    )

                    use_aggressive_mode_only_profit = st.checkbox(
                        "激进模式只用盈利部分", value=True,
                        help="启用后激进模式只用盈利部分开仓，保护本金"
                    )

                    # 阶梯仓位模式下也需要设置这些值用于向后兼容
                    allocation_pct = conservative_base_ratio
                    fixed_amount = 1000.0
            with c2:
                contract_multiplier = st.number_input("合约倍数", min_value=0.0, value=1.0, step=0.5)
                slippage_pct = st.number_input("滑点百分比", min_value=0.0, max_value=10.0, value=0.05, step=0.01)
            with c3:
                force_close_pct = st.number_input("强制平仓百分比", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
                trigger_order = st.selectbox("触发顺序", ["保守（先不利）", "乐观（先有利）"], index=0)

            funds_cfg = {
                "position_mode": str(position_mode),
                "initial_equity": float(initial_equity),
                "allocation_pct": float(allocation_pct),
                "fixed_amount": float(fixed_amount),
                "contract_multiplier": float(contract_multiplier),
                "slippage_pct": float(slippage_pct),
                "force_close_pct": float(force_close_pct),
                "trigger_order": str(trigger_order),
                # 阶梯仓位策略参数
                "conservative_base_ratio": float(conservative_base_ratio),
                "aggressive_threshold_pct": float(aggressive_threshold_pct),
                "conservative_threshold_pct": float(conservative_threshold_pct),
                "use_aggressive_mode_only_profit": bool(use_aggressive_mode_only_profit),
            }

    st.markdown("---")
    exec_mode = st.radio("🚀 运行模式", ["前台运行 (需保持浏览器开启)", "后台运行 (可关闭浏览器)"], horizontal=True)

    if st.button("开始回测", type="primary"):
        if not state.get("tasks"):
            st.error("当前没有任务，请先在「任务来源」上传或生成任务！")
            return

        tasks = list(state["tasks"])
        base_url = engine.normalize_base_url(str(cfg["backend_url"]))
        analyze_path = str(cfg["analyze_path"])
        if not analyze_path.startswith("/"):
            analyze_path = "/" + analyze_path

        defaults = {
            "asset": "",
            "timeframe": "",
            "end_date": "",
            "end_time": "",
            "kline_count": int(cfg["default_kline_count"]),
            "future_kline_count": int(cfg["default_future_kline_count"]),
            "ai_version": str(cfg["default_ai_version"]),
            "data_method": str(cfg["default_data_method"]),
        }

        output_csv = os.path.abspath(output_path)
        
        # --- 后台运行逻辑 ---
        if "后台" in exec_mode:
            agent_model, graph_model = store.load_env_models()
            daemon_cfg = {
                "tasks_file": "", # 稍后设置
                "output_file": output_csv,
                "backend_url": base_url,
                "analyze_path": analyze_path,
                "concurrency": int(cfg["concurrency"]),
                "timeout": float(cfg["timeout"]),
                "retries": int(cfg["retries"]),
                "hold_threshold": float(cfg["hold_threshold"]),
                "defaults": defaults,
                "backtest_mode": backtest_mode,
                "funds_cfg": funds_cfg,
                "agent_model": agent_model,
                "graph_model": graph_model,
            }
            
            # 保存临时任务文件
            temp_tasks_path = os.path.join(store._tools_dir(), "data", "temp_daemon_tasks.csv")
            try:
                pd.DataFrame(tasks).to_csv(temp_tasks_path, index=False)
            except Exception as e:
                st.error(f"保存任务文件失败: {e}")
                return
                
            daemon_cfg["tasks_file"] = temp_tasks_path
            store.save_daemon_config(daemon_cfg)
            
            # 启动进程
            script_path = os.path.join(store._tools_dir(), "batch_backtest_daemon.py")
            cmd = f'python "{script_path}"'
            
            try:
                if platform.system() == "Windows":
                    # Windows: CREATE_NEW_PROCESS_GROUP = 0x00000200
                    subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                else:
                    # Linux: nohup ... &
                    # Use setsid to create a new session group so it doesn't die when parent (Streamlit) dies
                    subprocess.Popen(
                        ['nohup', 'python', script_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        preexec_fn=os.setsid
                    )
                
                st.success("后台任务已启动！正在切换到监控模式...")
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"启动后台进程失败: {e}")
            return

        # --- 前台运行逻辑 (保持原样) ---
        st.warning("回测运行期间请勿切换左侧菜单页面，否则会导致进度视图丢失！")

        state["bt_last_output_csv"] = output_csv
        state["bt_last_summary"] = None
        state["bt_last_rows"] = []

        existing_keys = set()
        if not rerun:
            existing_header, existing_keys = engine.load_existing_keys(output_csv)
            if existing_header and existing_header != core.OUTPUT_FIELDNAMES:
                st.warning(f"检测到输出CSV表头已变更，正在原地迁移：{output_csv}")
                engine.migrate_output_csv_in_place(output_csv, core.OUTPUT_FIELDNAMES)
                _, existing_keys = engine.load_existing_keys(output_csv)

        engine.ensure_output_header(output_csv, core.OUTPUT_FIELDNAMES)

        to_run = []
        skipped_count = 0
        if rerun:
            to_run = tasks
        else:
            for row in tasks:
                try:
                    key = engine.task_key_from_row(row, defaults)
                    if key in existing_keys:
                        skipped_count += 1
                        continue
                    to_run.append(row)
                except Exception:
                    to_run.append(row)

        st.info(f"任务总数：{len(tasks)} | 将执行：{len(to_run)} | 跳过：{skipped_count}")
        if not to_run:
            summary = {
                "total_tasks": len(tasks),
                "run_tasks": 0,
                "skipped_tasks": skipped_count,
                "failed": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "wins_1": 0,
                "losses_1": 0,
                "win_rate_1": 0.0,
                "wins_2": 0,
                "losses_2": 0,
                "win_rate_2": 0.0,
                "total_duration_s": 0.0,
            }
            state["bt_last_summary"] = summary
            state["next_page"] = "结果"
            st.rerun()
            return

        batch_row = {k: "" for k in core.OUTPUT_FIELDNAMES}
        batch_row["error"] = f"=== 新批次开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==="
        try:
            engine.append_output_row(output_csv, core.OUTPUT_FIELDNAMES, batch_row)
        except PermissionError:
            st.error(f"❌ 写入批次分隔行失败！请关闭文件：{output_csv}")
        except Exception as e:
            st.error(f"❌ 写入批次分隔行出错：{e}")

        csv_writer = engine.CsvWriter(output_csv, core.OUTPUT_FIELDNAMES)
        csv_writer.start()

        progress_bar = st.progress(0)
        status_text = st.empty()
        metrics_placeholder = st.empty()
        result_table = st.empty()

        completed = 0
        start_time = time.time()
        stats_wins_1 = 0
        stats_losses_1 = 0
        stats_wins_2 = 0
        stats_losses_2 = 0
        failed = 0

        equity = float(funds_cfg["initial_equity"]) if funds_cfg else None

        def handle_one_result(result_row: dict[str, Any]) -> None:
            nonlocal completed, stats_wins_1, stats_losses_1, stats_wins_2, stats_losses_2, failed

            agent_model, graph_model = store.load_env_models()
            # 优先使用 engine 从 API 响应 llm_config 中提取的模型信息，
            # .env 读取仅作为回退（当 API 响应中缺失时）。
            if agent_model and not result_row.get("AGENT_MODEL"):
                result_row["AGENT_MODEL"] = agent_model
            if graph_model and not result_row.get("GRAPH_MODEL"):
                result_row["GRAPH_MODEL"] = graph_model

            result_row["回测模式"] = backtest_mode

            is_correct_1 = core.classify_is_correct(result_row.get("is_correct_1"))
            is_correct_2 = core.classify_is_correct(result_row.get("is_correct_2"))
            if is_correct_1 == "True":
                stats_wins_1 += 1
            elif is_correct_1 == "False":
                stats_losses_1 += 1

            if is_correct_2 == "True":
                stats_wins_2 += 1
            elif is_correct_2 == "False":
                stats_losses_2 += 1

            if is_correct_1 == "Error" or is_correct_2 == "Error":
                failed += 1

            total_valid_1 = stats_wins_1 + stats_losses_1
            total_valid_2 = stats_wins_2 + stats_losses_2
            win_rate_1 = (stats_wins_1 / total_valid_1 * 100.0) if total_valid_1 > 0 else 0.0
            win_rate_2 = (stats_wins_2 / total_valid_2 * 100.0) if total_valid_2 > 0 else 0.0
            result_row["cumulative_win_rate"] = f"{win_rate_2:.2f}%" if total_valid_2 > 0 else "无"
            result_row["cumulative_win_rate_1"] = f"{win_rate_1:.2f}%" if total_valid_1 > 0 else "无"
            result_row["cumulative_win_rate_2"] = f"{win_rate_2:.2f}%" if total_valid_2 > 0 else "无"

            try:
                csv_writer.write(result_row)
            except Exception as e:
                st.error(f"❌ 写入CSV出错：{e}")

            completed += 1
            progress_bar.progress(completed / len(to_run))

            elapsed = time.time() - start_time
            avg_time = elapsed / completed if completed > 0 else 0.0
            eta = avg_time * (len(to_run) - completed)
            status_text.text(f"正在处理：{result_row.get('task_id') or '未知'} | 预计剩余：{eta:.1f} 秒")

            if backtest_mode == "带资金回测":
                c1, c2, c3, c4, c5 = metrics_placeholder.columns(5)
                c1.metric("已完成", f"{completed}/{len(to_run)}")
                c2.metric("K1胜率", f"{win_rate_1:.2f}%")
                c3.metric("K2胜率", f"{win_rate_2:.2f}%")
                c4.metric("K2胜场/负场", f"{stats_wins_2}/{stats_losses_2}")
                eq_val = result_row.get("资金_当前")
                c5.metric("当前资金", eq_val if eq_val not in (None, "") else "无")
            else:
                c1, c2, c3, c4 = metrics_placeholder.columns(4)
                c1.metric("已完成", f"{completed}/{len(to_run)}")
                c2.metric("K1胜率", f"{win_rate_1:.2f}%")
                c3.metric("K2胜率", f"{win_rate_2:.2f}%")
                c4.metric("K2胜场/负场", f"{stats_wins_2}/{stats_losses_2}")

            state["bt_last_rows"].append(result_row)
            if len(state["bt_last_rows"]) > 200:
                state["bt_last_rows"] = state["bt_last_rows"][-200:]

            df = pd.DataFrame(state["bt_last_rows"][-10:])
            display_cols = [c for c in core.DEFAULT_EXECUTE_DISPLAY_COLS if c in df.columns]
            if display_cols:
                result_table.dataframe(core.style_df(df[display_cols]), use_container_width=True)
            else:
                result_table.dataframe(core.style_df(df), use_container_width=True)

        if backtest_mode == "带资金回测":
            if funds_cfg is None:
                st.error("请先填写资金回测参数")
                return
            # 初始化仓位状态
            position_state = {"is_aggressive": False}
            for i, row in enumerate(to_run):
                result_row, equity = engine.run_one_task_with_funds(
                    base_url=base_url,
                    analyze_path=analyze_path,
                    timeout_s=float(cfg["timeout"]),
                    retries=int(cfg["retries"]),
                    backoff_s=1.0,
                    hold_threshold=float(cfg["hold_threshold"]),
                    row=row,
                    defaults=defaults,
                    initial_equity=float(funds_cfg["initial_equity"]),
                    equity_before=float(equity) if equity is not None else float(funds_cfg["initial_equity"]),
                    position_mode=str(funds_cfg.get("position_mode", "固定百分比")),
                    allocation_pct=float(funds_cfg["allocation_pct"]),
                    fixed_amount=float(funds_cfg.get("fixed_amount", 1000.0)),
                    contract_multiplier=float(funds_cfg["contract_multiplier"]),
                    slippage_pct=float(funds_cfg["slippage_pct"]),
                    force_close_pct=float(funds_cfg["force_close_pct"]),
                    trigger_order=str(funds_cfg["trigger_order"]),
                    # 阶梯仓位策略参数
                    position_state=position_state,
                    conservative_base_ratio=float(funds_cfg.get("conservative_base_ratio", 30.0)),
                    aggressive_threshold_pct=float(funds_cfg.get("aggressive_threshold_pct", 150.0)),
                    conservative_threshold_pct=float(funds_cfg.get("conservative_threshold_pct", 110.0)),
                    use_aggressive_mode_only_profit=bool(funds_cfg.get("use_aggressive_mode_only_profit", True)),
                )
                # 更新仓位状态
                position_state["is_aggressive"] = result_row.get("_is_aggressive", False)
                handle_one_result(result_row)
        else:
            result_iterator = engine.run_tasks_concurrently(
                base_url,
                analyze_path,
                float(cfg["timeout"]),
                int(cfg["retries"]),
                1.0,
                float(cfg["hold_threshold"]),
                to_run,
                defaults,
                max_workers=int(cfg["concurrency"]),
            )
            for result_row in result_iterator:
                handle_one_result(result_row)

        csv_writer.stop()

        st.success("回测完成！")
        st.balloons()

        total_valid_1 = stats_wins_1 + stats_losses_1
        total_valid_2 = stats_wins_2 + stats_losses_2
        final_win_rate_1 = (stats_wins_1 / total_valid_1 * 100.0) if total_valid_1 > 0 else 0.0
        final_win_rate_2 = (stats_wins_2 / total_valid_2 * 100.0) if total_valid_2 > 0 else 0.0
        total_duration_s = round(time.time() - start_time, 3)
        funds_initial = None
        funds_final = None
        funds_pnl = None
        funds_pnl_pct = None
        if backtest_mode == "带资金回测" and funds_cfg is not None:
            try:
                funds_initial = float(funds_cfg["initial_equity"])
            except Exception:
                funds_initial = None
            try:
                if equity is not None:
                    funds_final = float(equity)
            except Exception:
                funds_final = None
            if funds_initial is not None and funds_final is not None:
                funds_pnl = funds_final - funds_initial
                if funds_initial != 0:
                    funds_pnl_pct = funds_pnl / funds_initial * 100.0
        state["bt_last_summary"] = {
            "total_tasks": len(tasks),
            "run_tasks": completed,
            "skipped_tasks": skipped_count,
            "failed": failed,
            "wins": stats_wins_2,
            "losses": stats_losses_2,
            "win_rate": final_win_rate_2,
            "wins_1": stats_wins_1,
            "losses_1": stats_losses_1,
            "win_rate_1": final_win_rate_1,
            "wins_2": stats_wins_2,
            "losses_2": stats_losses_2,
            "win_rate_2": final_win_rate_2,
            "total_duration_s": total_duration_s,
            "funds_initial": funds_initial,
            "funds_final": funds_final,
            "funds_pnl": funds_pnl,
            "funds_pnl_pct": funds_pnl_pct,
        }
        state["next_page"] = "结果"
        st.rerun()


def render_results(*, cfg: dict[str, Any], state: MutableMapping[str, Any], core: Any) -> None:
    st.markdown("### 最近一次运行结果")

    with st.expander("📂 加载历史结果", expanded=True):
        c_res1, c_res2 = st.columns([3, 1])
        default_path = state.get("bt_last_output_csv") or os.path.join("tools", "backtest_results.csv")
        load_path = c_res1.text_input("结果文件路径", value=default_path)
        if c_res2.button("🔄 加载/刷新结果"):
            if os.path.exists(load_path):
                try:
                    df = pd.read_csv(load_path)
                    state["bt_last_output_csv"] = load_path
                    rows = df.to_dict("records")
                    state["bt_last_rows"] = rows

                    s = core.compute_summary_from_rows(rows)
                    summary = {
                        "total_tasks": "未知",
                        "run_tasks": len(rows),
                        "skipped_tasks": "未知",
                        "failed": s["failed"],
                        "wins": s["wins"],
                        "losses": s["losses"],
                        "win_rate": s["win_rate"],
                        "wins_1": s.get("wins_1", 0),
                        "losses_1": s.get("losses_1", 0),
                        "win_rate_1": s.get("win_rate_1", 0.0),
                        "wins_2": s.get("wins_2", s["wins"]),
                        "losses_2": s.get("losses_2", s["losses"]),
                        "win_rate_2": s.get("win_rate_2", s["win_rate"]),
                        "total_duration_s": 0.0,
                        "funds_initial": s.get("funds_initial"),
                        "funds_final": s.get("funds_final"),
                        "funds_pnl": s.get("funds_pnl"),
                        "funds_pnl_pct": s.get("funds_pnl_pct"),
                    }
                    state["bt_last_summary"] = summary
                    st.success(f"成功加载 {len(rows)} 条记录")
                    st.rerun()
                except Exception as e:
                    st.error(f"读取失败: {e}")
            else:
                st.error("文件不存在")

    summary = state.get("bt_last_summary")
    output_csv = state.get("bt_last_output_csv")

    if not summary and not output_csv:
        st.info("暂无结果。请先在“执行回测”运行一次。")
        return

    col_r1, col_r2, col_r3, col_r4, col_r5 = st.columns(5)
    col_r1.metric("本次运行", summary.get("run_tasks") if summary else "无")
    col_r2.metric("跳过", summary.get("skipped_tasks") if summary else "无")
    col_r3.metric("失败", summary.get("failed") if summary else "无")
    col_r4.metric("K1胜率", f"{summary.get('win_rate_1', summary.get('win_rate', 0.0)):.2f}%" if summary else "无")
    col_r5.metric("K2胜率", f"{summary.get('win_rate_2', summary.get('win_rate', 0.0)):.2f}%" if summary else "无")
    col_r6, col_r7, col_r8 = st.columns(3)
    col_r6.metric("K1胜场/负场", f"{summary.get('wins_1', 0)}/{summary.get('losses_1', 0)}" if summary else "无")
    col_r7.metric("K2胜场/负场", f"{summary.get('wins_2', summary.get('wins', 0))}/{summary.get('losses_2', summary.get('losses', 0))}" if summary else "无")
    col_r8.metric("总耗时", f"{summary.get('total_duration_s', 0.0):.1f}秒" if summary else "无")

    if summary:
        funds_initial = summary.get("funds_initial")
        funds_final = summary.get("funds_final")
        funds_pnl = summary.get("funds_pnl")
        funds_pnl_pct = summary.get("funds_pnl_pct")
        if funds_initial is not None and funds_final is not None:
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            col_f1.metric("初始资金", f"{float(funds_initial):.2f}")
            col_f2.metric("最后资金", f"{float(funds_final):.2f}")
            if funds_pnl is not None:
                col_f3.metric("总盈亏", f"{float(funds_pnl):+.2f}")
            else:
                col_f3.metric("总盈亏", "N/A")
            if funds_pnl_pct is not None:
                col_f4.metric("总盈亏百分比", f"{float(funds_pnl_pct):+.2f}%")
            else:
                col_f4.metric("总盈亏百分比", "N/A")

    if state.get("bt_last_rows"):
        df = pd.DataFrame(state["bt_last_rows"])
        display_cols = [c for c in core.DEFAULT_RESULTS_DISPLAY_COLS if c in df.columns]
        st.dataframe(core.style_df(df[display_cols] if display_cols else df), use_container_width=True)

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if output_csv and os.path.exists(output_csv):
            with open(output_csv, "rb") as f:
                st.download_button(
                    label="下载结果文件",
                    data=f,
                    file_name=os.path.basename(output_csv),
                    mime="text/csv",
                )
    with col_b2:
        if st.button("清空结果显示", type="secondary"):
            state["bt_last_output_csv"] = ""
            state["bt_last_summary"] = None
            state["bt_last_rows"] = []


def _normalize_assets_input_state(state: MutableMapping[str, Any]) -> None:
    state["gen_assets_input"] = core.normalize_assets_input_text(state.get("gen_assets_input", ""))


def _add_favs_callback(state: MutableMapping[str, Any], selected: list[str]) -> None:
    current = state.get("gen_assets_input", "")
    if not selected:
        return
    assets = core.parse_assets_input(current)
    for a in selected:
        if a not in assets:
            assets.append(a)
    state["gen_assets_input"] = ", ".join(assets)
