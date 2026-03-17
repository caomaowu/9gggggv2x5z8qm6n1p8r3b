import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import json
import os
import sys
import threading
from pathlib import Path
from dotenv import load_dotenv

# 添加后端目录到 sys.path
backend_dir = Path(__file__).parent.parent.parent
sys.path.append(str(backend_dir))

try:
    from app.core.config import create_llm_client
    from app.agents.decision.decision_agent_original import ORIGINAL_PROMPT_TEMPLATE
    from app.agents.decision.decision_agent_lite import LITE_PROMPT_TEMPLATE
except ImportError as e:
    messagebox.showerror("Import Error", f"Failed to import backend modules:\n{e}\n\nPlease run this script from the project root or ensure dependencies are installed.")
    sys.exit(1)

class PromptTuningApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Decision Agent Prompt Tuning Lab (Local GUI)")
        self.root.geometry("1200x800")
        
        # 加载环境变量
        env_path = backend_dir / ".env"
        print(f"Loading .env from: {env_path}")
        load_dotenv(env_path)
        
        # 强制重载 Config 以确保环境变量生效
        from app.core.config import reload_config
        reload_config()
        
        self.context_data = None
        self.current_prompt_template = tk.StringVar(value="original")
        
        self.create_widgets()
        
    def create_widgets(self):
        # 顶部控制面板
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        ttk.Button(top_frame, text="1. 加载历史报告 (JSON)", command=self.load_context).pack(side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(top_frame, text="未加载文件", foreground="gray")
        self.file_label.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(top_frame, text="Prompt 版本:").pack(side=tk.LEFT, padx=(30, 5))
        ttk.Radiobutton(top_frame, text="Original", variable=self.current_prompt_template, value="original", command=self.update_prompt_editor).pack(side=tk.LEFT)
        ttk.Radiobutton(top_frame, text="Lite", variable=self.current_prompt_template, value="lite", command=self.update_prompt_editor).pack(side=tk.LEFT)
        
        ttk.Button(top_frame, text="🚀 运行测试", command=self.run_test, style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        
        # 主体分屏
        paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧：Prompt 编辑器
        left_frame = ttk.LabelFrame(paned_window, text="Prompt 模板编辑区")
        paned_window.add(left_frame, weight=1)
        
        self.prompt_editor = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, font=("Consolas", 10))
        self.prompt_editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.update_prompt_editor()
        
        # 右侧分屏 (上下文预览 + 输出结果)
        right_paned = ttk.PanedWindow(paned_window, orient=tk.VERTICAL)
        paned_window.add(right_paned, weight=1)
        
        # 右上：提取的上下文预览
        ctx_frame = ttk.LabelFrame(right_paned, text="提取的上下文数据 (只读预览)")
        right_paned.add(ctx_frame, weight=1)
        
        self.context_viewer = scrolledtext.ScrolledText(ctx_frame, wrap=tk.WORD, font=("Consolas", 9), bg="#f0f0f0")
        self.context_viewer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 右下：LLM 输出结果
        out_frame = ttk.LabelFrame(right_paned, text="LLM 决策结果")
        right_paned.add(out_frame, weight=2)
        
        self.output_viewer = scrolledtext.ScrolledText(out_frame, wrap=tk.WORD, font=("Consolas", 10), bg="#1e1e1e", fg="#00ff00")
        self.output_viewer.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def update_prompt_editor(self):
        self.prompt_editor.delete("1.0", tk.END)
        if self.current_prompt_template.get() == "original":
            self.prompt_editor.insert(tk.END, ORIGINAL_PROMPT_TEMPLATE)
        else:
            self.prompt_editor.insert(tk.END, LITE_PROMPT_TEMPLATE)
            
    def load_context(self):
        # 默认打开 history 目录
        init_dir = backend_dir / "data" / "history"
        if not init_dir.exists():
            init_dir = backend_dir
            
        file_path = filedialog.askopenfilename(
            initialdir=init_dir,
            title="选择历史报告 JSON",
            filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 提取数据
            self.context_data = {
                "stock_name": data.get("stock_name", "Unknown"),
                "time_frame": data.get("time_frame", "Unknown"),
                "price_summary": data.get("price_summary", "No price summary available."),
                "price_info_str": data.get("price_info_str", "No price info available."),
                "latest_price_str": str(data.get("latest_price", "Unknown")),
                "future_kline_data": data.get("future_kline_data", []),
                "indicator_report": "",
                "pattern_report": "",
                "trend_report": ""
            }
            
            # 兼容不同格式
            if "indicator_report" in data:
                self.context_data["indicator_report"] = data["indicator_report"]
            if "pattern_report" in data:
                self.context_data["pattern_report"] = data["pattern_report"]
            if "trend_report" in data:
                self.context_data["trend_report"] = data["trend_report"]
                
            if "analysis_results" in data:
                results = data["analysis_results"]
                if "Indicator" in results and "indicator_report" in results["Indicator"]:
                    self.context_data["indicator_report"] = results["Indicator"]["indicator_report"]
                if "Pattern" in results and "pattern_report" in results["Pattern"]:
                    self.context_data["pattern_report"] = results["Pattern"]["pattern_report"]
                if "Trend" in results and "trend_report" in results["Trend"]:
                    self.context_data["trend_report"] = results["Trend"]["trend_report"]
            
            # 显示提取的数据
            self.context_viewer.config(state=tk.NORMAL)
            self.context_viewer.delete("1.0", tk.END)
            self.context_viewer.insert(tk.END, json.dumps(self.context_data, ensure_ascii=False, indent=2))
            self.context_viewer.config(state=tk.DISABLED)
            
            self.file_label.config(text=os.path.basename(file_path), foreground="blue")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file:\n{e}")

    def run_test(self):
        if not self.context_data:
            messagebox.showwarning("Warning", "请先加载历史报告 JSON 文件！")
            return
            
        # 获取当前编辑器中的 Prompt
        template = self.prompt_editor.get("1.0", tk.END).strip()
        
        # 格式化
        try:
            prompt = template.format(
                stock_name=self.context_data.get("stock_name", "Unknown"),
                time_frame=self.context_data.get("time_frame", "Unknown"),
                price_summary=self.context_data.get("price_summary", ""),
                price_info_str=self.context_data.get("price_info_str", ""),
                latest_price_str=self.context_data.get("latest_price_str", ""),
                indicator_report=self.context_data.get("indicator_report", ""),
                pattern_report=self.context_data.get("pattern_report", ""),
                trend_report=self.context_data.get("trend_report", "")
            )
        except Exception as e:
            messagebox.showerror("Prompt Format Error", f"Prompt 格式化失败，请检查占位符 {{}} 是否正确:\n{e}")
            return
            
        self.output_viewer.delete("1.0", tk.END)
        self.output_viewer.insert(tk.END, "正在初始化 LLM...\n")
        self.root.update_idletasks()
        
        # 使用线程避免阻塞 UI
        threading.Thread(target=self._call_llm, args=(prompt,), daemon=True).start()
        
    def _call_llm(self, prompt):
        try:
            llm = create_llm_client(role="agent")
            
            self.output_viewer.insert(tk.END, "请求已发送，等待响应中...\n\n")
            self.output_viewer.yview(tk.END)
            
            response = llm.invoke(prompt)
            
            self.output_viewer.insert(tk.END, "====== 🤖 最终决策结果 ======\n")
            self.output_viewer.insert(tk.END, response.content)
            self.output_viewer.insert(tk.END, "\n=============================\n\n")
            
            # 评估未来走势
            self._evaluate_decision(response.content)
            
            self.output_viewer.yview(tk.END)
            
        except Exception as e:
            self.output_viewer.insert(tk.END, f"\n❌ 调用失败:\n{str(e)}\n")
            self.output_viewer.yview(tk.END)

    def _evaluate_decision(self, ai_output):
        """解析 AI 输出并与未来 K 线比对验证"""
        try:
            # 尝试从输出中提取 JSON
            import re
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', ai_output, re.DOTALL)
            if json_match:
                decision_json = json.loads(json_match.group(1))
            else:
                # 尝试直接解析
                decision_json = json.loads(ai_output)
                
            action = decision_json.get("decision", "").upper()
            if not action or action not in ["LONG", "SHORT", "HOLD"]:
                self.output_viewer.insert(tk.END, "⚠️ 无法解析有效的交易方向 (LONG/SHORT/HOLD)\n")
                return
                
        except Exception:
            self.output_viewer.insert(tk.END, "⚠️ 无法解析 AI 输出的 JSON，请检查 Prompt 格式约束\n")
            return

        future_data = self.context_data.get("future_kline_data", [])
        if not future_data:
            self.output_viewer.insert(tk.END, "⚠️ 当前报告中没有未来 K 线数据，无法验证预测结果。\n")
            return
            
        try:
            latest_price = float(self.context_data.get("latest_price_str", 0))
        except ValueError:
            self.output_viewer.insert(tk.END, "⚠️ 无法获取当前最新价格，无法验证。\n")
            return

        # 分析未来走势 - 只看前两根 K 线
        k1 = future_data[0] if len(future_data) > 0 else None
        k2 = future_data[1] if len(future_data) > 1 else None
        
        self.output_viewer.insert(tk.END, "====== 📈 未来走势验证 (前两根 K 线) ======\n")
        self.output_viewer.insert(tk.END, f"AI 预测方向: {action}\n")
        self.output_viewer.insert(tk.END, f"当前基准价格: {latest_price}\n\n")

        # 验证 K1 (仅收盘价)
        if k1:
            k1_close = float(k1.get('close', 0))
            k1_pct = ((k1_close - latest_price) / latest_price) * 100
            
            k1_result = "❌ 失败"
            if action == "LONG":
                if k1_close > latest_price:
                    k1_result = "✅ 成功 (收盘盈利)"
            elif action == "SHORT":
                if k1_close < latest_price:
                    k1_result = "✅ 成功 (收盘盈利)"
            elif action == "HOLD":
                k1_result = "⏸️ 观望"
                
            self.output_viewer.insert(tk.END, f"K1 (下一根收盘): {k1_result}\n")
            self.output_viewer.insert(tk.END, f"   Price: {k1_close} ({k1_pct:+.2f}%)\n")
        else:
            self.output_viewer.insert(tk.END, "K1: 无数据\n")

        # 验证 K2 (仅收盘价)
        if k2:
            k2_close = float(k2.get('close', 0))
            k2_pct = ((k2_close - latest_price) / latest_price) * 100
            
            k2_result = "❌ 失败"
            if action == "LONG":
                if k2_close > latest_price:
                    k2_result = "✅ 成功 (收盘盈利)"
            elif action == "SHORT":
                if k2_close < latest_price:
                    k2_result = "✅ 成功 (收盘盈利)"
            elif action == "HOLD":
                k2_result = "⏸️ 观望"
                
            self.output_viewer.insert(tk.END, f"K2 (下两根收盘): {k2_result}\n")
            self.output_viewer.insert(tk.END, f"   Price: {k2_close} ({k2_pct:+.2f}%)\n")
        else:
            self.output_viewer.insert(tk.END, "K2: 无数据\n")

        self.output_viewer.insert(tk.END, "\n")

if __name__ == "__main__":
    # 添加简单的样式
    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    
    app = PromptTuningApp(root)
    root.mainloop()
