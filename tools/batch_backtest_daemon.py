import json
import os
import sys
import time
import traceback
import signal
from datetime import datetime
from typing import Any, Dict, List

# Ensure tools directory is in sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from batch_backtest_app import core, engine, store

def handle_signal(signum, frame):
    print(f"[{datetime.now()}] Received signal {signum}, stopping...")
    # Clean up status file
    if os.path.exists(store.DAEMON_STATUS_FILE):
        os.remove(store.DAEMON_STATUS_FILE)
    
    # Update progress to stopped
    try:
        p = store.load_daemon_progress()
        p["status"] = "已停止"
        p["is_running"] = False
        store.save_daemon_progress(p)
    except:
        pass
        
    sys.exit(0)

def main():
    # Register signal handlers for Linux/Unix
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    print(f"[{datetime.now()}] Daemon started, PID: {os.getpid()}")
    
    # 1. Update Status (Running)
    store.save_daemon_status({
        "pid": os.getpid(),
        "start_time": datetime.now().isoformat(),
        "last_heartbeat": datetime.now().isoformat()
    })

    try:
        # 2. Load Config
        config = store.load_daemon_config()
        if not config:
            raise ValueError("Config file not found or empty")

        tasks_file = config.get("tasks_file")
        output_csv = config.get("output_file")
        
        if not tasks_file or not os.path.exists(tasks_file):
            raise FileNotFoundError(f"Tasks file not found: {tasks_file}")
            
        tasks = engine.read_tasks(tasks_file)
        if not tasks:
            raise ValueError("No tasks found in tasks file")

        # 3. Prepare Execution
        engine.ensure_output_header(output_csv, core.OUTPUT_FIELDNAMES)
        
        # Write batch separator
        batch_row = {k: "" for k in core.OUTPUT_FIELDNAMES}
        batch_row["error"] = f"=== 后台批次开始 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (PID: {os.getpid()}) ==="
        engine.append_output_row(output_csv, core.OUTPUT_FIELDNAMES, batch_row)

        csv_writer = engine.CsvWriter(output_csv, core.OUTPUT_FIELDNAMES)
        csv_writer.start()

        # Initialize Stats
        total_tasks = len(tasks)
        completed = 0
        stats_wins_1 = 0
        stats_losses_1 = 0
        stats_wins_2 = 0
        stats_losses_2 = 0
        failed = 0
        
        funds_cfg = config.get("funds_cfg") or {}
        equity = funds_cfg.get("initial_equity", 10000.0)
        
        # Initial Progress Write
        progress = {
            "is_running": True,
            "current_task_id": "",
            "current_task_index": 0,
            "total_tasks": total_tasks,
            "completed_count": 0,
            "failed_count": 0,
            "start_time": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "current_asset": "",
            "current_timeframe": "",
            "current_end_date": "",
            "current_end_time": "",
            "stats_wins": 0,
            "stats_losses": 0,
            "stats_wins_1": 0,
            "stats_losses_1": 0,
            "stats_wins_2": 0,
            "stats_losses_2": 0,
            "equity": equity,
            "status": "正在运行"
        }
        store.save_daemon_progress(progress)

        # 4. Run Loop
        backtest_mode = config.get("backtest_mode", "普通回测")
        funds_cfg = config.get("funds_cfg")
        
        # Position state for funds mode
        position_state = {"is_aggressive": False}

        # Generator
        if backtest_mode == "带资金回测" and funds_cfg:
             # Serial execution for funds mode (must be sequential)
             # Reuse engine logic but we might need to handle it manually if engine doesn't support generator for sequential with state
             # Actually engine.run_tasks_concurrently uses ThreadPoolExecutor which is NOT suitable for sequential funds backtest if order matters.
             # However, looking at engine.py, run_tasks_concurrently is concurrent. 
             # Wait, if backtest_mode is "带资金回测", we usually want sequential execution to track equity?
             # Let's check how the UI handles it.
             # The UI uses run_tasks_concurrently even for funds mode? 
             # No, let's check UI logic again.
             pass
        
        # Re-checking UI logic from previous search...
        # The UI calls engine.run_tasks_concurrently for ALL modes.
        # But wait, run_one_task_with_funds returns equity_after.
        # If running concurrently, equity tracking will be messed up because they run in parallel.
        # Ah, the previous code search showed run_tasks_concurrently yields results.
        # BUT, for "带资金回测", strict sequential execution is usually required if position sizing depends on current equity.
        # The current UI implementation seems to pass `equity` (current value) to `run_one_task_with_funds`.
        # If it runs concurrently, they all get the SAME equity at start of batch? 
        # Actually, looking at `engine.py`, `run_tasks_concurrently` uses ThreadPoolExecutor.
        # This implies the current UI implementation of "带资金回测" might be flawed if it uses concurrency > 1.
        # However, for this Daemon, I will strictly follow the config.
        # If config['concurrency'] is 1, it's sequential.
        
        concurrency = config.get("concurrency", 1)
        
        # For funds mode, force concurrency = 1 to ensure correctness, or trust the user config?
        # User config has "concurrency" input.
        # If I want to be safe, I should respect the logic.
        
        defaults = config.get("defaults", {})
        
        # Use engine's generator
        # Note: We need to handle "带资金回测" specially if we want to update equity dynamically.
        # The engine.run_tasks_concurrently does NOT support passing updated equity to next task.
        # It submits all tasks at once.
        # So, for "带资金回测", we must run manually in a loop if we want real equity updates.
        
        if backtest_mode == "带资金回测":
            # Manual Sequential Loop for Funds Mode
            print("Running in Funds Mode (Sequential)...")
            current_equity = equity
            
            for i, row in enumerate(tasks):
                # Update heartbeat
                store.save_daemon_status({
                    "pid": os.getpid(),
                    "start_time": progress["start_time"],
                    "last_heartbeat": datetime.now().isoformat()
                })
                
                # Prepare args
                # We need to call run_one_task_with_funds directly
                try:
                    res, new_equity = engine.run_one_task_with_funds(
                        base_url=config["backend_url"],
                        analyze_path=config["analyze_path"],
                        timeout_s=config["timeout"],
                        retries=config["retries"],
                        backoff_s=0.5,
                        hold_threshold=config["hold_threshold"],
                        row=row,
                        defaults=defaults,
                        initial_equity=funds_cfg["initial_equity"],
                        equity_before=current_equity,
                        position_mode=funds_cfg["position_mode"],
                        allocation_pct=funds_cfg["allocation_pct"],
                        fixed_amount=funds_cfg["fixed_amount"],
                        contract_multiplier=funds_cfg["contract_multiplier"],
                        slippage_pct=funds_cfg["slippage_pct"],
                        force_close_pct=funds_cfg["force_close_pct"],
                        trigger_order=funds_cfg["trigger_order"],
                        position_state=position_state,
                        conservative_base_ratio=funds_cfg.get("conservative_base_ratio", 30.0),
                        aggressive_threshold_pct=funds_cfg.get("aggressive_threshold_pct", 150.0),
                        conservative_threshold_pct=funds_cfg.get("conservative_threshold_pct", 110.0),
                        use_aggressive_mode_only_profit=funds_cfg.get("use_aggressive_mode_only_profit", True),
                    )
                    
                    current_equity = new_equity
                    
                    # Process Result
                    # 优先使用 engine 从 API 响应 llm_config 提取的模型信息，
                    # daemon config 中的值仅作回退。
                    if not res.get("AGENT_MODEL"):
                        res["AGENT_MODEL"] = config.get("agent_model", "")
                    if not res.get("GRAPH_MODEL"):
                        res["GRAPH_MODEL"] = config.get("graph_model", "")
                    res["回测模式"] = backtest_mode
                    
                    # Update Stats
                    is_correct_1 = core.classify_is_correct(res.get("is_correct_1"))
                    is_correct_2 = core.classify_is_correct(res.get("is_correct_2"))
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
                    res["cumulative_win_rate"] = f"{win_rate_2:.2f}%" if total_valid_2 > 0 else "无"
                    res["cumulative_win_rate_1"] = f"{win_rate_1:.2f}%" if total_valid_1 > 0 else "无"
                    res["cumulative_win_rate_2"] = f"{win_rate_2:.2f}%" if total_valid_2 > 0 else "无"
                    
                    # Write to CSV
                    csv_writer.write(res)
                    
                    # Update Progress
                    completed += 1
                    progress.update({
                        "current_task_id": res.get("task_id", ""),
                        "current_task_index": i + 1,
                        "completed_count": completed,
                        "failed_count": failed,
                        "stats_wins": stats_wins_2,
                        "stats_losses": stats_losses_2,
                        "stats_wins_1": stats_wins_1,
                        "stats_losses_1": stats_losses_1,
                        "stats_wins_2": stats_wins_2,
                        "stats_losses_2": stats_losses_2,
                        "equity": current_equity,
                        "last_update": datetime.now().isoformat(),
                        "current_asset": res.get("asset", ""),
                        "current_timeframe": res.get("timeframe", ""),
                        "current_end_date": res.get("end_date", ""),
                        "current_end_time": res.get("end_time", ""),
                    })
                    store.save_daemon_progress(progress)

                except Exception as e:
                    print(f"Task failed: {e}")
                    traceback.print_exc()
                    failed += 1
                    progress["failed_count"] = failed
                    store.save_daemon_progress(progress)

        else:
            # Concurrent Mode for Normal Backtest
            print(f"Running in Normal Mode (Concurrency: {concurrency})...")
            
            # Use engine's generator
            iterator = engine.run_tasks_concurrently(
                base_url=config["backend_url"],
                analyze_path=config["analyze_path"],
                timeout_s=config["timeout"],
                retries=config["retries"],
                backoff_s=0.5,
                hold_threshold=config["hold_threshold"],
                rows=tasks,
                defaults=defaults,
                max_workers=concurrency,
            )
            
            for i, res in enumerate(iterator):
                # Update heartbeat
                store.save_daemon_status({
                    "pid": os.getpid(),
                    "start_time": progress["start_time"],
                    "last_heartbeat": datetime.now().isoformat()
                })
                
                # Process Result
                res["AGENT_MODEL"] = config.get("agent_model", "")
                res["GRAPH_MODEL"] = config.get("graph_model", "")
                res["回测模式"] = backtest_mode
                
                # Update Stats
                is_correct_1 = core.classify_is_correct(res.get("is_correct_1"))
                is_correct_2 = core.classify_is_correct(res.get("is_correct_2"))
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
                res["cumulative_win_rate"] = f"{win_rate_2:.2f}%" if total_valid_2 > 0 else "无"
                res["cumulative_win_rate_1"] = f"{win_rate_1:.2f}%" if total_valid_1 > 0 else "无"
                res["cumulative_win_rate_2"] = f"{win_rate_2:.2f}%" if total_valid_2 > 0 else "无"

                # Write to CSV
                csv_writer.write(res)

                # Update Progress
                completed += 1
                progress.update({
                    "current_task_id": res.get("task_id", ""),
                    "current_task_index": completed, # Approximation for concurrent
                    "completed_count": completed,
                    "failed_count": failed,
                    "stats_wins": stats_wins_2,
                    "stats_losses": stats_losses_2,
                    "stats_wins_1": stats_wins_1,
                    "stats_losses_1": stats_losses_1,
                    "stats_wins_2": stats_wins_2,
                    "stats_losses_2": stats_losses_2,
                    "last_update": datetime.now().isoformat(),
                    "current_asset": res.get("asset", ""),
                    "current_timeframe": res.get("timeframe", ""),
                    "current_end_date": res.get("end_date", ""),
                    "current_end_time": res.get("end_time", ""),
                })
                store.save_daemon_progress(progress)

        csv_writer.stop()

        # 5. Finish
        progress["status"] = "已完成"
        progress["is_running"] = False
        store.save_daemon_progress(progress)
        print("Done.")

    except Exception as e:
        print(f"Daemon Error: {e}")
        traceback.print_exc()
        
        # Write Error to Progress
        try:
            p = store.load_daemon_progress()
            p["status"] = f"出错: {str(e)}"
            p["is_running"] = False
            store.save_daemon_progress(p)
        except:
            pass
            
    finally:
        # Cleanup Status
        # store.save_daemon_status({}) # Or keep it for inspection? 
        # Better to keep it but mark as done? No, remove PID so UI knows it's gone.
        # But if we crash, PID file might remain. UI should check if PID exists.
        # Let's just clear it to be clean.
        if os.path.exists(store.DAEMON_STATUS_FILE):
            os.remove(store.DAEMON_STATUS_FILE)

if __name__ == "__main__":
    main()
