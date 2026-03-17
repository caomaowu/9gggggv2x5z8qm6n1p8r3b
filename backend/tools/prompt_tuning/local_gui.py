from __future__ import annotations

import json
import queue
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from dotenv import load_dotenv


backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

from app.agents.decision.decision_agent_lite import LITE_PROMPT_TEMPLATE
from app.agents.decision.decision_agent_original import ORIGINAL_PROMPT_TEMPLATE
from app.core.config import reload_config
from prompt_tuning_engine import (
    BatchBacktestRunner,
    BatchRunConfig,
    BacktestPointResult,
    ContextLoader,
    DecisionRunner,
    PromptRunResult,
)


class PromptTuningApp:
    EVENT_POLL_MS = 100

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Decision Agent Prompt Tuning Lab")
        self.root.geometry("1360x860")

        env_path = backend_dir / ".env"
        load_dotenv(env_path)
        reload_config()

        self.context_loader = ContextLoader()
        self.single_context = None
        self.batch_folder_path = ""
        self.batch_summary = None
        self.batch_results = []
        self.active_task = None
        self.worker_thread = None
        self.cancel_event = None
        self.pending_close = False
        self.ui_queue: queue.Queue[dict] = queue.Queue()
        self.batch_live_counts = {}

        self.mode_var = tk.StringVar(value="single")
        self.current_prompt_template = tk.StringVar(value="original")
        self.file_label_var = tk.StringVar(value="未加载 JSON 文件")
        self.batch_folder_label_var = tk.StringVar(value="未选择文件夹")
        self.export_dir_var = tk.StringVar(value=self._build_default_export_dir())
        self.concurrency_var = tk.StringVar(value="3")
        self.batch_stats_var = tk.StringVar(value="批量统计：尚未开始")

        self._build_layout()
        self.update_prompt_editor()
        self._update_mode_ui()
        self.root.after(self.EVENT_POLL_MS, self._process_ui_events)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_default_export_dir(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return str((Path(__file__).resolve().parent / "exports" / timestamp))

    def _build_layout(self) -> None:
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top_frame, text="运行模式：").pack(side=tk.LEFT)
        self.mode_buttons = [
            ttk.Radiobutton(
                top_frame,
                text="单个 JSON",
                variable=self.mode_var,
                value="single",
                command=self._activate_single_mode,
            ),
            ttk.Radiobutton(
                top_frame,
                text="文件夹批量回测",
                variable=self.mode_var,
                value="batch",
                command=self._activate_batch_mode,
            ),
        ]
        for button in self.mode_buttons:
            button.pack(side=tk.LEFT, padx=4)

        ttk.Label(top_frame, text="Prompt 版本：").pack(side=tk.LEFT, padx=(20, 4))
        self.prompt_version_buttons = [
            ttk.Radiobutton(
                top_frame,
                text="Original",
                variable=self.current_prompt_template,
                value="original",
                command=self.update_prompt_editor,
            ),
            ttk.Radiobutton(
                top_frame,
                text="Lite",
                variable=self.current_prompt_template,
                value="lite",
                command=self.update_prompt_editor,
            ),
        ]
        for button in self.prompt_version_buttons:
            button.pack(side=tk.LEFT, padx=4)

        # Container for dynamic controls (single vs batch) to ensure correct packing order
        self.controls_container = ttk.Frame(self.root)
        self.controls_container.pack(side=tk.TOP, fill=tk.X)

        self.single_controls = ttk.Frame(self.controls_container, padding=(10, 0, 10, 8))
        self.batch_controls = ttk.Frame(self.controls_container, padding=(10, 0, 10, 8))

        self.load_single_button = ttk.Button(
            self.single_controls,
            text="重新选择 JSON",
            command=self.load_context,
        )
        self.load_single_button.pack(side=tk.LEFT)

        ttk.Label(
            self.single_controls,
            textvariable=self.file_label_var,
            foreground="blue",
        ).pack(side=tk.LEFT, padx=10)

        self.run_single_button = ttk.Button(
            self.single_controls,
            text="运行单个测试",
            command=self.run_single_test,
        )
        self.run_single_button.pack(side=tk.RIGHT)

        batch_row1 = ttk.Frame(self.batch_controls)
        batch_row1.pack(fill=tk.X, pady=(0, 6))
        self.select_batch_folder_button = ttk.Button(
            batch_row1,
            text="重新选择文件夹",
            command=self.select_batch_folder,
        )
        self.select_batch_folder_button.pack(side=tk.LEFT)

        ttk.Label(
            batch_row1,
            textvariable=self.batch_folder_label_var,
            foreground="blue",
        ).pack(side=tk.LEFT, padx=10)

        batch_row2 = ttk.Frame(self.batch_controls)
        batch_row2.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(batch_row2, text="并发数：").pack(side=tk.LEFT)
        self.concurrency_spinbox = ttk.Spinbox(
            batch_row2,
            from_=1,
            to=8,
            width=6,
            textvariable=self.concurrency_var,
        )
        self.concurrency_spinbox.pack(side=tk.LEFT, padx=(4, 12))

        self.select_export_dir_button = ttk.Button(
            batch_row2,
            text="选择导出目录",
            command=self.select_export_dir,
        )
        self.select_export_dir_button.pack(side=tk.LEFT)

        ttk.Label(batch_row2, textvariable=self.export_dir_var).pack(
            side=tk.LEFT, padx=10
        )

        batch_row3 = ttk.Frame(self.batch_controls)
        batch_row3.pack(fill=tk.X, pady=(0, 6))
        self.run_batch_button = ttk.Button(
            batch_row3,
            text="启动批量回测",
            command=self.run_batch_test,
        )
        self.run_batch_button.pack(side=tk.LEFT)

        self.cancel_batch_button = ttk.Button(
            batch_row3,
            text="取消批量任务",
            command=self.cancel_batch_run,
            state=tk.DISABLED,
        )
        self.cancel_batch_button.pack(side=tk.LEFT, padx=8)

        ttk.Label(batch_row3, textvariable=self.batch_stats_var).pack(
            side=tk.LEFT, padx=10
        )

        self.progress_bar = ttk.Progressbar(
            self.batch_controls,
            mode="determinate",
            maximum=1,
        )
        self.progress_bar.pack(fill=tk.X)

        paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame = ttk.LabelFrame(paned_window, text="Prompt 模板编辑")
        paned_window.add(left_frame, weight=1)
        self.prompt_editor = scrolledtext.ScrolledText(
            left_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
        )
        self.prompt_editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        right_paned = ttk.PanedWindow(paned_window, orient=tk.VERTICAL)
        paned_window.add(right_paned, weight=1)

        preview_frame = ttk.LabelFrame(right_paned, text="上下文 / 批量预览")
        right_paned.add(preview_frame, weight=1)
        self.context_viewer = scrolledtext.ScrolledText(
            preview_frame,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#f3f3f3",
        )
        self.context_viewer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        output_frame = ttk.LabelFrame(right_paned, text="输出与日志")
        right_paned.add(output_frame, weight=2)
        self.output_viewer = scrolledtext.ScrolledText(
            output_frame,
            wrap=tk.WORD,
            font=("Consolas", 10),
            bg="#1e1e1e",
            fg="#d9fdd3",
        )
        self.output_viewer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def update_prompt_editor(self) -> None:
        self.prompt_editor.delete("1.0", tk.END)
        if self.current_prompt_template.get() == "original":
            self.prompt_editor.insert(tk.END, ORIGINAL_PROMPT_TEMPLATE)
        else:
            self.prompt_editor.insert(tk.END, LITE_PROMPT_TEMPLATE)

    def _update_mode_ui(self) -> None:
        self.single_controls.pack_forget()
        self.batch_controls.pack_forget()
        if self.mode_var.get() == "single":
            self.single_controls.pack(side=tk.TOP, fill=tk.X)
        else:
            self.batch_controls.pack(side=tk.TOP, fill=tk.X)

    def _activate_single_mode(self) -> None:
        self.mode_var.set("single")
        self._update_mode_ui()
        if self.active_task is None:
            self.load_context()

    def _activate_batch_mode(self) -> None:
        self.mode_var.set("batch")
        self._update_mode_ui()
        if self.active_task is None:
            self.select_batch_folder()

    def _set_running_state(self, task: str | None) -> None:
        self.active_task = task
        running = task is not None
        base_state = tk.DISABLED if running else tk.NORMAL
        for button in self.mode_buttons + self.prompt_version_buttons:
            button.configure(state=base_state)

        self.load_single_button.configure(state=base_state)
        self.run_single_button.configure(
            state=tk.DISABLED if running else tk.NORMAL
        )
        self.select_batch_folder_button.configure(state=base_state)
        self.select_export_dir_button.configure(state=base_state)
        self.concurrency_spinbox.configure(state=base_state)
        self.run_batch_button.configure(state=tk.DISABLED if running else tk.NORMAL)
        self.cancel_batch_button.configure(
            state=tk.NORMAL if task == "batch" else tk.DISABLED
        )

    def _append_output(self, text: str) -> None:
        self.output_viewer.insert(tk.END, text + "\n")
        self.output_viewer.see(tk.END)

    def _set_preview(self, payload: dict) -> None:
        self.context_viewer.delete("1.0", tk.END)
        self.context_viewer.insert(
            tk.END, json.dumps(payload, ensure_ascii=False, indent=2)
        )

    def load_context(self) -> None:
        init_dir = backend_dir / "data" / "history"
        file_path = filedialog.askopenfilename(
            initialdir=init_dir if init_dir.exists() else backend_dir,
            title="选择历史报告 JSON",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*")),
        )
        if not file_path:
            return

        try:
            self.single_context = self.context_loader.load(file_path)
        except Exception as exc:
            messagebox.showerror("加载失败", f"无法加载文件：\n{exc}")
            return

        self.file_label_var.set(Path(file_path).name)
        self._set_preview(self.single_context.to_preview_dict())
        self._append_output(f"[单个] 已加载 {Path(file_path).name}")

    def select_batch_folder(self) -> None:
        init_dir = backend_dir / "data" / "history"
        folder_path = filedialog.askdirectory(
            initialdir=init_dir if init_dir.exists() else backend_dir,
            title="选择批量回测文件夹",
        )
        if not folder_path:
            return

        folder = Path(folder_path)
        files = sorted(path.name for path in folder.glob("*.json") if path.is_file())
        self.batch_folder_path = str(folder)
        self.batch_folder_label_var.set(f"{folder.name}（{len(files)} 个 JSON）")
        self._set_preview(
            {
                "mode": "batch",
                "folder": str(folder.resolve()),
                "json_file_count": len(files),
                "files": files[:50],
            }
        )
        self._append_output(
            f"[批量] 已选择文件夹 {folder.resolve()}，当前目录共 {len(files)} 个 JSON"
        )

    def select_export_dir(self) -> None:
        current = Path(self.export_dir_var.get())
        initial_dir = current.parent if current.suffix else current
        folder_path = filedialog.askdirectory(
            initialdir=initial_dir if initial_dir.exists() else backend_dir,
            title="选择导出目录",
        )
        if folder_path:
            self.export_dir_var.set(folder_path)

    def run_single_test(self) -> None:
        if self.active_task is not None:
            return
        if self.single_context is None:
            messagebox.showwarning("提示", "请先加载单个 JSON 文件。")
            return

        template = self.prompt_editor.get("1.0", tk.END).strip()
        self.output_viewer.delete("1.0", tk.END)
        self._append_output("[单个] 开始调用 LLM...")
        self._set_running_state("single")

        self.worker_thread = threading.Thread(
            target=self._single_worker,
            args=(self.single_context, template, self.current_prompt_template.get()),
            daemon=True,
        )
        self.worker_thread.start()

    def _single_worker(self, context, template: str, prompt_version: str) -> None:
        try:
            result = DecisionRunner().run(context, template, prompt_version)
            self.ui_queue.put({"type": "single_completed", "result": result})
        except Exception as exc:
            self.ui_queue.put({"type": "single_failed", "error": str(exc)})

    def run_batch_test(self) -> None:
        if self.active_task is not None:
            return
        if not self.batch_folder_path:
            messagebox.showwarning("提示", "请先选择批量回测文件夹。")
            return

        try:
            concurrency = max(1, min(8, int(self.concurrency_var.get())))
        except ValueError:
            messagebox.showerror("参数错误", "并发数必须是 1 到 8 的整数。")
            return

        template = self.prompt_editor.get("1.0", tk.END).strip()
        export_dir = self.export_dir_var.get().strip() or self._build_default_export_dir()
        self.export_dir_var.set(export_dir)

        self.output_viewer.delete("1.0", tk.END)
        self.progress_bar.configure(maximum=1, value=0)
        self.batch_live_counts = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }
        self.batch_summary = None
        self.batch_results = []
        self.batch_stats_var.set("批量统计：运行中")
        self.cancel_event = threading.Event()
        self._set_running_state("batch")

        self.worker_thread = threading.Thread(
            target=self._batch_worker,
            args=(
                template,
                self.current_prompt_template.get(),
                self.batch_folder_path,
                export_dir,
                concurrency,
            ),
            daemon=True,
        )
        self.worker_thread.start()

    def _batch_worker(
        self,
        template: str,
        prompt_version: str,
        folder_path: str,
        export_dir: str,
        concurrency: int,
    ) -> None:
        try:
            runner = BatchBacktestRunner()
            runner.run(
                BatchRunConfig(
                    input_dir=folder_path,
                    prompt_template=template,
                    prompt_version=prompt_version,
                    export_dir=export_dir,
                    concurrency=concurrency,
                ),
                cancel_event=self.cancel_event,
                event_callback=self.ui_queue.put,
            )
        except Exception as exc:
            self.ui_queue.put({"type": "batch_failed", "error": str(exc)})

    def cancel_batch_run(self) -> None:
        if self.active_task != "batch" or self.cancel_event is None:
            return
        self.cancel_event.set()
        self.cancel_batch_button.configure(state=tk.DISABLED)
        self._append_output("[批量] 已请求取消，将停止提交新的任务。")

    def _process_ui_events(self) -> None:
        while True:
            try:
                event = self.ui_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)

        if self.pending_close and not self._is_worker_alive():
            self.root.destroy()
            return

        self.root.after(self.EVENT_POLL_MS, self._process_ui_events)

    def _handle_event(self, event: dict) -> None:
        event_type = event.get("type")
        if event_type == "single_completed":
            self._handle_single_completed(event["result"])
        elif event_type == "single_failed":
            self._set_running_state(None)
            self.worker_thread = None
            self._append_output(f"[单个] 运行失败：{event['error']}")
        elif event_type == "batch_started":
            total_files = event["total_files"]
            self.progress_bar.configure(maximum=max(total_files, 1), value=0)
            self._append_output(
                f"[批量] 启动完成，发现 {total_files} 个 JSON，导出目录：{event['export_dir']}"
            )
        elif event_type == "file_started":
            self._append_output(f"[批量] 开始处理 {event['file_name']}")
        elif event_type == "file_completed":
            self._handle_batch_file_completed(event)
        elif event_type == "batch_completed":
            self._handle_batch_completed(event)
        elif event_type == "batch_failed":
            self._set_running_state(None)
            self.worker_thread = None
            self._append_output(f"[批量] 运行失败：{event['error']}")

    def _handle_single_completed(self, result: PromptRunResult) -> None:
        self._set_running_state(None)
        self.worker_thread = None
        self._append_output("====== 单个测试结果 ======")
        self._append_output(f"状态：{result.status}")
        self._append_output(f"决策：{result.decision or '未解析'}")
        self._append_output(f"解析模式：{result.decision_parse_mode}")
        self._append_output(f"耗时：{result.elapsed_ms} ms")
        if result.error_message:
            self._append_output(f"错误：{result.error_message}")
        if result.raw_response:
            self._append_output("")
            self._append_output("------ LLM 原始输出 ------")
            self._append_output(result.raw_response)
        self._append_output("")
        self._append_output(self._format_backtest_line("K1", result.k1_result))
        self._append_output(self._format_backtest_line("K2", result.k2_result))

    def _handle_batch_file_completed(self, event: dict) -> None:
        result = event["result"]
        self.batch_results.append(result)
        self.batch_live_counts["processed"] += 1
        status = result["status"]
        if status == "success":
            self.batch_live_counts["success"] += 1
        elif status == "backtest_skipped":
            self.batch_live_counts["skipped"] += 1
        else:
            self.batch_live_counts["failed"] += 1

        self.progress_bar.configure(value=event["processed_count"])
        self.batch_stats_var.set(
            "批量统计：已处理 {processed} | 成功 {success} | 跳过 {skipped} | 失败 {failed}".format(
                **self.batch_live_counts
            )
        )
        self._append_output(
            "[批量] 完成 {file_name} | status={status} | decision={decision} | elapsed={elapsed}ms".format(
                file_name=event["file_name"],
                status=status,
                decision=result["decision"] or "N/A",
                elapsed=result["elapsed_ms"],
            )
        )

    def _handle_batch_completed(self, event: dict) -> None:
        self._set_running_state(None)
        self.worker_thread = None
        self.batch_summary = event["summary"]
        self.batch_results = event["results"]
        self.progress_bar.configure(value=self.batch_summary["total"])
        self.batch_stats_var.set(
            "批量统计：总数 {total} | 成功 {succeeded} | 跳过 {backtest_skipped} | 失败 {failed}".format(
                **self.batch_summary
            )
        )
        status_text = "已取消" if event.get("cancelled") else "已完成"
        self._append_output(
            f"[批量] {status_text}。总数={self.batch_summary['total']}，成功={self.batch_summary['succeeded']}，"
            f"跳过={self.batch_summary['backtest_skipped']}，失败={self.batch_summary['failed']}"
        )
        self._append_output(
            f"[批量] K1 胜率: {self.batch_summary.get('k1_win_rate', 0):.2%} ({self.batch_summary.get('k1_win_count', 0)}胜)"
        )
        self._append_output(
            f"[批量] K2 胜率: {self.batch_summary.get('k2_win_rate', 0):.2%} ({self.batch_summary.get('k2_win_count', 0)}胜)"
        )
        self._append_output(f"[批量] 导出 JSON：{self.batch_summary['export_json_path']}")
        self._append_output(f"[批量] 导出 CSV：{self.batch_summary['export_csv_path']}")

    def _format_backtest_line(self, label: str, point: BacktestPointResult) -> str:
        if point.outcome == "missing":
            return f"{label}: 无数据"
        pct = "N/A" if point.pct is None else f"{point.pct:+.2f}%"
        return f"{label}: close={point.close} | pct={pct} | outcome={point.outcome}"

    def _is_worker_alive(self) -> bool:
        return self.worker_thread is not None and self.worker_thread.is_alive()

    def _on_close(self) -> None:
        if not self._is_worker_alive():
            self.root.destroy()
            return

        self.pending_close = True
        if self.cancel_event is not None:
            self.cancel_event.set()
        self._append_output("[系统] 正在等待后台任务安全退出...")


if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    PromptTuningApp(root)
    root.mainloop()
