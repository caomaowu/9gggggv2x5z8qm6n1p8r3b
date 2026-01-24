import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

TOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from batch_backtest_app import engine, queue_manager, store, core

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(TOOLS_DIR, "data", "daemon.log"), encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    "backend_url": "http://localhost:8000/api/v1",
    "analyze_path": "/analyze/",
    "concurrency": 6,
    "task_delay": 1.6,
    "timeout": 180.0,
    "retries": 2,
    "hold_threshold": 0.002,
    "default_kline_count": 40,
    "default_future_kline_count": 13,
    "default_ai_version": "original",
    "default_data_method": "to_end",
    "initial_equity": 10000.0,
    "allocation_pct": 100.0,
    "contract_multiplier": 1.0,
    "slippage_pct": 0.05,
    "force_close_pct": 5.0,
    "trigger_order": "保守（先不利）",
    "output_path": os.path.join("tools", "backtest_results.csv"),
}


def load_config() -> Dict[str, Any]:
    config_file = os.path.join(TOOLS_DIR, "data", "daemon_config.json")
    if not os.path.exists(config_file):
        return DEFAULT_CONFIG.copy()

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
            result = DEFAULT_CONFIG.copy()
            result.update(config)
            return result
    except Exception as e:
        logger.warning(f"加载配置文件失败，使用默认配置: {e}")
        return DEFAULT_CONFIG.copy()


def save_config(config: Dict[str, Any]) -> None:
    config_file = os.path.join(TOOLS_DIR, "data", "daemon_config.json")
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")


def update_heartbeat(status_file: str, pid: int, start_time: str) -> None:
    try:
        status = {
            "pid": pid,
            "start_time": start_time,
            "last_heartbeat": datetime.now().isoformat(),
        }
        with queue_manager.FileLock(status_file.replace(".json", ".lock"), timeout=5.0):
            with open(status_file, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"更新心跳失败: {e}")


def update_progress(
    progress_file: str,
    task: Dict[str, Any],
    task_index: int,
    total_tasks: int,
    completed_count: int,
    failed_count: int,
    stats_wins: int,
    stats_losses: int,
    equity: Optional[float],
    is_running: bool = True,
) -> None:
    try:
        progress = {
            "is_running": is_running,
            "current_task_id": task.get("task_id", ""),
            "current_task_index": task_index,
            "total_tasks": total_tasks,
            "completed_count": completed_count,
            "failed_count": failed_count,
            "start_time": datetime.now().isoformat() if is_running else None,
            "last_update": datetime.now().isoformat(),
            "current_asset": task.get("asset", ""),
            "current_timeframe": task.get("timeframe", ""),
            "current_end_date": task.get("end_date", ""),
            "current_end_time": task.get("end_time", ""),
            "stats_wins": stats_wins,
            "stats_losses": stats_losses,
            "equity": equity,
        }
        with queue_manager.FileLock(progress_file.replace(".json", ".lock"), timeout=5.0):
            with open(progress_file, "w", encoding="utf-8") as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"更新进度失败: {e}")


def mark_progress_idle(progress_file: str) -> None:
    try:
        progress = queue_manager.load_progress()
        progress["is_running"] = False
        progress["status"] = "空闲"
        progress["last_update"] = datetime.now().isoformat()
        with queue_manager.FileLock(progress_file.replace(".json", ".lock"), timeout=5.0):
            with open(progress_file, "w", encoding="utf-8") as f:
                json.dump(progress, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"标记进度为空闲失败: {e}")


def run_one_task(
    config: Dict[str, Any],
    task: Dict[str, Any],
    output_csv: str,
    backtest_mode: str,
    funds_cfg: Optional[Dict[str, Any]],
    equity: Optional[float],
) -> tuple[Dict[str, Any], Optional[float]]:
    base_url = engine.normalize_base_url(str(config["backend_url"]))
    analyze_path = str(config["analyze_path"])
    if not analyze_path.startswith("/"):
        analyze_path = "/" + analyze_path

    defaults = {
        "asset": "",
        "timeframe": "",
        "end_date": "",
        "end_time": "",
        "kline_count": int(config["default_kline_count"]),
        "future_kline_count": int(config["default_future_kline_count"]),
        "ai_version": str(config["default_ai_version"]),
        "data_method": str(config["default_data_method"]),
    }

    task_row = {k: v for k, v in task.items() if not k.startswith("_")}

    try:
        if backtest_mode == "带资金回测" and funds_cfg:
            result_row, equity = engine.run_one_task_with_funds(
                base_url=base_url,
                analyze_path=analyze_path,
                timeout_s=float(config["timeout"]),
                retries=int(config["retries"]),
                backoff_s=1.0,
                hold_threshold=float(config["hold_threshold"]),
                row=task_row,
                defaults=defaults,
                initial_equity=float(funds_cfg["initial_equity"]),
                equity_before=float(equity) if equity is not None else float(funds_cfg["initial_equity"]),
                allocation_pct=float(funds_cfg["allocation_pct"]),
                contract_multiplier=float(funds_cfg["contract_multiplier"]),
                slippage_pct=float(funds_cfg["slippage_pct"]),
                force_close_pct=float(funds_cfg["force_close_pct"]),
                trigger_order=str(funds_cfg["trigger_order"]),
            )
        else:
            result_row = engine.run_one_task(
                base_url=base_url,
                analyze_path=analyze_path,
                timeout_s=float(config["timeout"]),
                retries=int(config["retries"]),
                backoff_s=1.0,
                hold_threshold=float(config["hold_threshold"]),
                row=task_row,
                defaults=defaults,
            )

        agent_model, graph_model = store.load_env_models()
        if agent_model:
            result_row["AGENT_MODEL"] = agent_model
        if graph_model:
            result_row["GRAPH_MODEL"] = graph_model

        result_row["回测模式"] = backtest_mode

        is_correct = core.classify_is_correct(result_row.get("is_correct"))
        total_valid = (result_row.get("stats_wins", 0) if isinstance(result_row.get("stats_wins"), int) else 0) + \
                     (result_row.get("stats_losses", 0) if isinstance(result_row.get("stats_losses"), int) else 0)
        win_rate = (result_row.get("stats_wins", 0) / total_valid * 100.0) if total_valid > 0 else 0.0
        result_row["cumulative_win_rate"] = f"{win_rate:.2f}%" if total_valid > 0 else "无"

        engine.append_output_row(output_csv, core.OUTPUT_FIELDNAMES, result_row)

        return result_row, equity

    except Exception as e:
        logger.error(f"执行任务失败 {task.get('task_id', '未知')}: {e}")

        error_row = {
            "task_id": task.get("task_id", ""),
            "asset": task.get("asset", ""),
            "timeframe": task.get("timeframe", ""),
            "end_date": task.get("end_date", ""),
            "end_time": task.get("end_time", ""),
            "分析时的价格": "N/A",
            "未来第一根K线的价格": "N/A",
            "未来第二根K线的价格": "N/A",
            "ai_decision": "ERROR",
            "is_correct": "Error",
            "profit_pct_1": "N/A",
            "profit_pct_2": "N/A",
            "duration_s": 0.0,
            "result_id": "",
            "ai_version": task.get("ai_version", ""),
            "data_method": task.get("data_method", ""),
            "kline_count": task.get("kline_count", 0),
            "future_kline_count": task.get("future_kline_count", 0),
            "error": str(e),
            "回测模式": backtest_mode,
        }

        if backtest_mode == "带资金回测" and funds_cfg:
            error_row["资金_初始"] = f"{float(funds_cfg['initial_equity']):.2f}"
            error_row["资金_当前"] = f"{float(equity) if equity else float(funds_cfg['initial_equity']):.2f}"
            error_row["下单金额"] = "0.00"
            error_row["仓位比例"] = f"{float(funds_cfg['allocation_pct']):.2f}%"
            error_row["合约倍数"] = f"{float(funds_cfg['contract_multiplier']):.4f}"
            error_row["滑点百分比"] = f"{float(funds_cfg['slippage_pct']):.4f}%"
            error_row["强制平仓百分比"] = f"{float(funds_cfg['force_close_pct']):.4f}%"
            error_row["名义金额"] = "0.00"
            error_row["成交数量"] = "0.00000000"
            error_row["成交开仓价"] = "N/A"
            error_row["成交平仓价"] = "N/A"
            error_row["平仓原因"] = "执行失败"
            error_row["本次盈亏"] = "+0.00"
            error_row["本次盈亏百分比"] = "N/A"

        try:
            engine.append_output_row(output_csv, core.OUTPUT_FIELDNAMES, error_row)
        except Exception as e2:
            logger.error(f"写入错误行失败: {e2}")

        return error_row, equity


def run_daemon() -> None:
    config = load_config()
    logger.info("守护进程启动")
    logger.info(f"配置: {json.dumps(config, indent=2, ensure_ascii=False)}")

    pid = os.getpid()
    start_time = datetime.now().isoformat()

    status_file = queue_manager.STATUS_FILE
    progress_file = queue_manager.PROGRESS_FILE
    output_csv = os.path.abspath(config["output_path"])

    queue_manager.save_status({
        "pid": pid,
        "start_time": start_time,
        "last_heartbeat": datetime.now().isoformat(),
    })

    engine.ensure_output_header(output_csv, core.OUTPUT_FIELDNAMES)

    backtest_mode = "普通回测"
    funds_cfg = None

    if config.get("backtest_mode") == "带资金回测":
        backtest_mode = "带资金回测"
        funds_cfg = {
            "initial_equity": float(config.get("initial_equity", 10000.0)),
            "allocation_pct": float(config.get("allocation_pct", 100.0)),
            "contract_multiplier": float(config.get("contract_multiplier", 1.0)),
            "slippage_pct": float(config.get("slippage_pct", 0.05)),
            "force_close_pct": float(config.get("force_close_pct", 5.0)),
            "trigger_order": str(config.get("trigger_order", "保守（先不利）")),
        }

    equity = funds_cfg["initial_equity"] if funds_cfg else None

    stats_wins = 0
    stats_losses = 0
    completed_count = 0
    failed_count = 0
    total_processed = 0

    heartbeat_counter = 0
    last_task_batch_id = None

    try:
        while True:
            heartbeat_counter += 1
            if heartbeat_counter % 10 == 0:
                update_heartbeat(status_file, pid, start_time)

            task = queue_manager.get_next_task()

            if task is None:
                mark_progress_idle(progress_file)
                time.sleep(5)
                continue

            # 确定当前任务的模式和配置
            current_backtest_mode = task.get("backtest_mode", backtest_mode)
            current_funds_cfg = task.get("funds_cfg", funds_cfg)

            batch_id = task.get("_batch_id")
            if batch_id != last_task_batch_id:
                batch_name = task.get("_batch_name", "未知批次")
                logger.info(f"开始处理新批次: {batch_name}")

                # 如果是资金回测模式，新批次开始时重置资金
                if current_backtest_mode == "带资金回测" and current_funds_cfg:
                    try:
                        equity = float(current_funds_cfg["initial_equity"])
                        logger.info(f"批次 {batch_id} (资金回测) 开始，重置初始资金为: {equity}")
                    except Exception as e:
                        logger.error(f"重置资金失败: {e}")

                batch_row = {k: "" for k in core.OUTPUT_FIELDNAMES}
                batch_row["error"] = f"=== 后台批次开始 {batch_name} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==="
                try:
                    engine.append_output_row(output_csv, core.OUTPUT_FIELDNAMES, batch_row)
                except Exception as e:
                    logger.error(f"写入批次分隔行失败: {e}")
                last_task_batch_id = batch_id

            logger.info(f"开始处理任务: {task.get('task_id', '未知')} - {task.get('asset', '')} {task.get('timeframe', '')} {task.get('end_date', '')}")

            queue_info = queue_manager.get_queue_info()
            total_tasks = queue_info.get("total_tasks_in_queue", 0) + completed_count + failed_count

            update_progress(
                progress_file,
                task,
                completed_count + failed_count + 1,
                total_tasks,
                completed_count,
                failed_count,
                stats_wins,
                stats_losses,
                equity,
            )

            try:
                result_row, equity = run_one_task(config, task, output_csv, current_backtest_mode, current_funds_cfg, equity)

                is_correct = core.classify_is_correct(result_row.get("is_correct"))
                if is_correct == "True":
                    stats_wins += 1
                elif is_correct == "False":
                    stats_losses += 1
                elif is_correct == "Error":
                    failed_count += 1

                completed_count += 1
                total_processed += 1

                logger.info(f"任务完成: {task.get('task_id', '未知')} - 决策: {result_row.get('ai_decision', '')} - 胜负: {is_correct}")

            except Exception as e:
                logger.error(f"任务执行异常 {task.get('task_id', '未知')}: {e}")
                failed_count += 1
                completed_count += 1
                total_processed += 1

            update_progress(
                progress_file,
                task,
                completed_count + failed_count,
                total_tasks,
                completed_count,
                failed_count,
                stats_wins,
                stats_losses,
                equity,
            )

            if total_processed % 10 == 0:
                update_heartbeat(status_file, pid, start_time)

            task_delay = float(config.get("task_delay", 1.6))
            if task_delay > 0:
                time.sleep(task_delay)

    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
    except Exception as e:
        logger.error(f"守护进程异常: {e}")
    finally:
        mark_progress_idle(progress_file)
        logger.info(f"守护进程停止。总计处理 {total_processed} 个任务，胜场 {stats_wins}，负场 {stats_losses}，失败 {failed_count}")


if __name__ == "__main__":
    run_daemon()
