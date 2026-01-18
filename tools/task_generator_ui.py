import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pandas as pd
import random
import os
from datetime import datetime, timedelta
import glob

# 配置默认路径
DEFAULT_DOC_DIR = os.path.join(os.path.dirname(__file__), 'doc')
DEFAULT_OUTPUT_DIR = os.path.dirname(__file__)

class TaskGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("随机任务生成器")
        self.root.geometry("1000x800")
        
        # 数据存储
        self.assets = []
        self.generated_tasks = []
        
        # 样式设置
        style = ttk.Style()
        style.configure("Bold.TLabel", font=("Microsoft YaHei", 9, "bold"))
        
        self._init_ui()
        self._load_default_files()

    def _init_ui(self):
        # 主布局：左侧配置，右侧预览
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 左侧面板
        left_frame = ttk.Frame(main_paned, width=350)
        main_paned.add(left_frame, weight=1)
        
        # 右侧面板
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)
        
        # === 左侧：配置区域 ===
        
        # 1. 数据源配置
        step1_frame = ttk.LabelFrame(left_frame, text="1. 数据源配置", padding=10)
        step1_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(step1_frame, text="源文件目录:").pack(anchor='w')
        self.doc_dir_var = tk.StringVar(value=DEFAULT_DOC_DIR)
        ttk.Entry(step1_frame, textvariable=self.doc_dir_var, state='readonly').pack(fill=tk.X, pady=2)
        
        ttk.Label(step1_frame, text="选择CSV文件:").pack(anchor='w', pady=(5,0))
        self.file_combo = ttk.Combobox(step1_frame, state="readonly")
        self.file_combo.pack(fill=tk.X, pady=2)
        self.file_combo.bind("<<ComboboxSelected>>", self.on_file_selected)
        
        self.asset_count_label = ttk.Label(step1_frame, text="当前加载资产数: 0", foreground="blue")
        self.asset_count_label.pack(anchor='w', pady=2)

        # 2. 随机参数设置
        step2_frame = ttk.LabelFrame(left_frame, text="2. 随机参数设置", padding=10)
        step2_frame.pack(fill=tk.X, pady=5)
        
        # 资产数量
        ttk.Label(step2_frame, text="抽取资产数量:").grid(row=0, column=0, sticky='w', pady=2)
        self.pick_count_var = tk.IntVar(value=5)
        ttk.Spinbox(step2_frame, from_=1, to=1000, textvariable=self.pick_count_var, width=10).grid(row=0, column=1, sticky='w', pady=2)
        
        # 日期范围
        ttk.Label(step2_frame, text="日期范围 (YYYY-MM-DD):").grid(row=1, column=0, columnspan=2, sticky='w', pady=(10,2))
        
        date_frame = ttk.Frame(step2_frame)
        date_frame.grid(row=2, column=0, columnspan=2, sticky='ew')
        
        self.start_date_var = tk.StringVar(value="2024-01-01")
        self.end_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=12).pack(side=tk.LEFT)
        ttk.Label(date_frame, text=" 至 ").pack(side=tk.LEFT)
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=12).pack(side=tk.LEFT)
        
        # 时间周期
        ttk.Label(step2_frame, text="时间周期 (Timeframe):").grid(row=3, column=0, sticky='w', pady=(10,2))
        self.timeframe_var = tk.StringVar(value="4h")
        self.timeframe_combo = ttk.Combobox(step2_frame, textvariable=self.timeframe_var, values=["30m", "1h", "4h", "1d"], state="readonly", width=10)
        self.timeframe_combo.grid(row=3, column=1, sticky='w', pady=2)
        
        # 其他固定参数
        ttk.Label(step2_frame, text="Kline Count:", font=("Arial", 8)).grid(row=4, column=0, sticky='w', pady=(10,2))
        self.kline_count_var = tk.IntVar(value=40)
        ttk.Entry(step2_frame, textvariable=self.kline_count_var, width=10).grid(row=4, column=1, sticky='w')
        
        ttk.Label(step2_frame, text="Future Kline:", font=("Arial", 8)).grid(row=5, column=0, sticky='w', pady=2)
        self.future_kline_var = tk.IntVar(value=13)
        ttk.Entry(step2_frame, textvariable=self.future_kline_var, width=10).grid(row=5, column=1, sticky='w')

        # 3. 操作按钮
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=20)
        
        ttk.Button(btn_frame, text="一键生成预览", command=self.generate_tasks, width=20).pack(pady=5)
        ttk.Button(btn_frame, text="清空预览", command=self.clear_tasks).pack(pady=5)

        # 4. 保存设置
        save_frame = ttk.LabelFrame(left_frame, text="4. 结果输出", padding=10)
        save_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(save_frame, text="文件名 (留空自动命名):").pack(anchor='w')
        self.filename_var = tk.StringVar()
        ttk.Entry(save_frame, textvariable=self.filename_var).pack(fill=tk.X, pady=5)
        ttk.Label(save_frame, text="格式: A[序号].csv", foreground="gray", font=("Arial", 8)).pack(anchor='w')
        
        ttk.Button(save_frame, text="保存为CSV", command=self.save_csv, state="normal").pack(fill=tk.X, pady=10)

        # === 右侧：预览区域 ===
        
        # 统计信息
        self.preview_info = ttk.Label(right_frame, text="预览: 0 条任务", font=("Microsoft YaHei", 10, "bold"))
        self.preview_info.pack(anchor='w', pady=(0, 10))
        
        # 表格
        cols = ("task_id", "asset", "timeframe", "end_date", "end_time", "kline_count", "future_kline_count", "ai_version", "data_method")
        self.tree = ttk.Treeview(right_frame, columns=cols, show='headings', height=25)
        
        # 设置列宽
        col_widths = {
            "task_id": 50, "asset": 80, "timeframe": 60, "end_date": 90, 
            "end_time": 70, "kline_count": 60, "future_kline_count": 60,
            "ai_version": 70, "data_method": 70
        }
        
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths.get(col, 80), anchor='center')
        
        # 滚动条
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_default_files(self):
        """扫描默认目录下的CSV文件"""
        if not os.path.exists(DEFAULT_DOC_DIR):
            try:
                os.makedirs(DEFAULT_DOC_DIR)
            except:
                pass
        
        files = glob.glob(os.path.join(DEFAULT_DOC_DIR, "*.csv"))
        filenames = [os.path.basename(f) for f in files]
        self.file_combo['values'] = filenames
        if filenames:
            self.file_combo.current(0)
            self.on_file_selected(None)

    def on_file_selected(self, event):
        """加载选中的CSV文件并解析Asset"""
        filename = self.file_combo.get()
        if not filename:
            return
            
        path = os.path.join(DEFAULT_DOC_DIR, filename)
        try:
            df = pd.read_csv(path)
            # 尝试寻找 asset 列
            # 常见的列名: "asset", "symbol", "币种代码"
            # 如果找不到，尝试找包含 USDT 的列
            asset_col = None
            for col in df.columns:
                if col.lower() in ['asset', 'symbol', '币种代码', 'coin']:
                    asset_col = col
                    break
            
            if not asset_col:
                # 暴力搜索第一列包含字符串的内容
                for col in df.columns:
                    if df[col].dtype == object:
                        asset_col = col
                        break
            
            if asset_col:
                raw_assets = df[asset_col].dropna().unique().tolist()
                # 格式转换: BTCUSDT -> BTC/USDT
                self.assets = []
                for a in raw_assets:
                    a = str(a).strip().upper()
                    if '/' not in a and a.endswith('USDT'):
                        a = a[:-4] + '/USDT'
                    self.assets.append(a)
                
                self.asset_count_label.config(text=f"当前加载资产数: {len(self.assets)}")
            else:
                messagebox.showerror("错误", "无法在文件中找到资产列")
                self.assets = []
                self.asset_count_label.config(text="当前加载资产数: 0")
                
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败: {str(e)}")

    def _generate_random_time(self, timeframe):
        """
        根据 timeframe 生成符合规则的时间
        - 4h: 3:55-3:59, 7:55-7:59, 11:55-11:59, 15:55-15:59, 19:55-19:59, 23:55-23:59
        - 1h: xx:55-xx:59
        - 30m: xx:25-xx:29, xx:55-xx:59
        - 1d: 23:55-23:59
        """
        minute = random.randint(55, 59)
        hour = 0
        
        if timeframe == '4h':
            # 4小时收盘点通常是 0, 4, 8, 12, 16, 20 (UTC)
            # 收盘前5分钟意味着小时数应该是 close_hour - 1
            # 比如 4点收盘，时间是 3:55
            # Close hours: 0, 4, 8, 12, 16, 20
            # Target hours: 23, 3, 7, 11, 15, 19
            target_hours = [23, 3, 7, 11, 15, 19]
            hour = random.choice(target_hours)
            
        elif timeframe == '1h':
            hour = random.randint(0, 23)
            # 分钟已经在上面固定为 55-59
            
        elif timeframe == '30m':
            hour = random.randint(0, 23)
            # 30m 收盘点: 00, 30
            # Ranges: xx:25-xx:29 (for 30 close), xx:55-xx:59 (for 00 close)
            base_min = random.choice([25, 55])
            minute = random.randint(base_min, base_min + 4)
            
        elif timeframe == '1d':
            hour = 23
            
        else:
            # 默认逻辑
            hour = random.randint(0, 23)
            minute = random.randint(55, 59)
            
        return f"{hour:02d}:{minute:02d}"

    def _get_random_date(self, start_str, end_str):
        try:
            start = datetime.strptime(start_str, "%Y-%m-%d")
            end = datetime.strptime(end_str, "%Y-%m-%d")
            delta = end - start
            if delta.days < 0:
                return start_str
            random_days = random.randint(0, delta.days)
            return (start + timedelta(days=random_days)).strftime("%Y-%m-%d")
        except:
            return datetime.now().strftime("%Y-%m-%d")

    def generate_tasks(self):
        if not self.assets:
            messagebox.showwarning("警告", "请先选择有效的数据源文件")
            return

        try:
            count = self.pick_count_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()
            tf = self.timeframe_var.get()
            k_count = self.kline_count_var.get()
            fut_count = self.future_kline_var.get()
            
            # 清空旧数据
            self.clear_tasks()
            
            # 清空文件名（确保下次保存时触发自动命名）
            self.filename_var.set("")
            
            # 随机抽取资产（允许重复抽取吗？通常 backtest 任务可以重复，但这里我们假设不重复如果 count <= total）
            if count <= len(self.assets):
                selected_assets = random.sample(self.assets, count)
            else:
                # 如果请求数量大于总数，则随机重复抽取
                selected_assets = [random.choice(self.assets) for _ in range(count)]
            
            for i, asset in enumerate(selected_assets, 1):
                task = {
                    "task_id": i,
                    "asset": asset,
                    "timeframe": tf,
                    "end_date": self._get_random_date(start_date, end_date),
                    "end_time": self._generate_random_time(tf),
                    "kline_count": k_count,
                    "future_kline_count": fut_count,
                    "ai_version": "original",
                    "data_method": "to_end"
                }
                self.generated_tasks.append(task)
                
                # 插入表格
                cols_order = ["task_id", "asset", "timeframe", "end_date", "end_time", "kline_count", "future_kline_count", "ai_version", "data_method"]
                values = [task[k] for k in cols_order]
                self.tree.insert('', 'end', values=values)
                
            self.preview_info.config(text=f"预览: {len(self.generated_tasks)} 条任务")
            
        except Exception as e:
            messagebox.showerror("生成失败", str(e))

    def clear_tasks(self):
        self.generated_tasks = []
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.preview_info.config(text="预览: 0 条任务")

    def save_csv(self):
        if not self.generated_tasks:
            messagebox.showwarning("警告", "没有可保存的任务，请先生成")
            return
            
        filename = self.filename_var.get().strip()
        
        # 自动命名逻辑
        if not filename:
            # 扫描 A[0-1000].csv
            existing_files = glob.glob(os.path.join(DEFAULT_OUTPUT_DIR, "A*.csv"))
            max_idx = 0
            for f in existing_files:
                base = os.path.basename(f)
                # 简单的正则匹配 A数字.csv
                try:
                    name_part = os.path.splitext(base)[0]
                    if name_part.startswith('A') and name_part[1:].isdigit():
                        idx = int(name_part[1:])
                        if idx > max_idx:
                            max_idx = idx
                except:
                    continue
            filename = f"A{max_idx + 1}.csv"
            
        if not filename.lower().endswith('.csv'):
            filename += '.csv'
            
        filepath = os.path.join(DEFAULT_OUTPUT_DIR, filename)
        
        try:
            df = pd.DataFrame(self.generated_tasks)
            # 确保列顺序
            cols_order = ["task_id", "asset", "timeframe", "end_date", "end_time", "kline_count", "future_kline_count", "ai_version", "data_method"]
            df = df[cols_order]
            df.to_csv(filepath, index=False)
            messagebox.showinfo("成功", f"文件已保存至:\n{filepath}")
            self.filename_var.set(filename) # 回填文件名
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

if __name__ == "__main__":
    root = tk.Tk()
    app = TaskGeneratorApp(root)
    root.mainloop()
