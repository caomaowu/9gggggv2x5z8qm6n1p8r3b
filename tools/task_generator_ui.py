import calendar
from datetime import datetime, timedelta
import glob
import os
import random
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import concurrent.futures
import requests
from dotenv import load_dotenv

import pandas as pd

# 配置默认路径
DEFAULT_DOC_DIR = os.path.join(os.path.dirname(__file__), 'doc')
DEFAULT_OUTPUT_DIR = os.path.dirname(__file__)

# 加载环境变量
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', '.env')
load_dotenv(env_path)
API_URL = os.getenv("MARKET_DATA_API_URL", "https://webui.caomaowu.lol")
API_TOKEN = os.getenv("MARKET_DATA_API_TOKEN", "")

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
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        left_container = ttk.Frame(main_paned, width=380)
        main_paned.add(left_container, weight=2)
        
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)
        
        left_canvas = tk.Canvas(left_container, borderwidth=0, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient=tk.VERTICAL, command=left_canvas.yview)
        left_scrollable = ttk.Frame(left_canvas)
        
        def _on_frame_configure(event):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
        
        def _on_mousewheel(event):
            if event.delta > 0:
                left_canvas.yview_scroll(-1, "units")
            else:
                left_canvas.yview_scroll(1, "units")
        
        def _bind_mousewheel(event):
            left_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            left_canvas.unbind_all("<MouseWheel>")
        
        left_scrollable.bind("<Configure>", _on_frame_configure)
        left_canvas.bind("<Enter>", _bind_mousewheel)
        left_canvas.bind("<Leave>", _unbind_mousewheel)
        
        left_canvas.create_window((0, 0), window=left_scrollable, anchor="nw")
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        left_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        left_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 1. 数据源配置
        step1_frame = ttk.LabelFrame(left_scrollable, text="1. 数据源配置", padding=10)
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
        step2_frame = ttk.LabelFrame(left_scrollable, text="2. 随机参数设置", padding=10)
        step2_frame.pack(fill=tk.X, pady=5)
        
        # 资产数量
        ttk.Label(step2_frame, text="抽取资产数量:").grid(row=0, column=0, sticky='w', pady=2)
        self.pick_count_var = tk.IntVar(value=5)
        ttk.Spinbox(step2_frame, from_=1, to=1000, textvariable=self.pick_count_var, width=10).grid(row=0, column=1, sticky='w', pady=2)
        
        # 日期范围
        ttk.Label(step2_frame, text="日期范围 (YYYY-MM-DD):").grid(row=1, column=0, columnspan=2, sticky='w', pady=(10,2))
        
        date_frame = ttk.Frame(step2_frame)
        date_frame.grid(row=2, column=0, columnspan=2, sticky='ew')
        
        self.start_date_var = tk.StringVar(value="2025-01-01")
        self.end_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        
        start_entry = ttk.Entry(date_frame, textvariable=self.start_date_var, width=12)
        start_entry.pack(side=tk.LEFT)
        start_entry.bind("<FocusOut>", lambda e: self._normalize_date_entry(self.start_date_var))
        start_entry.bind("<Return>", lambda e: self._normalize_date_entry(self.start_date_var))
        ttk.Button(date_frame, text="📅", width=3, command=lambda: self._open_date_picker(self.start_date_var)).pack(side=tk.LEFT, padx=(2, 4))
        ttk.Label(date_frame, text=" 至 ").pack(side=tk.LEFT)
        end_entry = ttk.Entry(date_frame, textvariable=self.end_date_var, width=12)
        end_entry.pack(side=tk.LEFT)
        end_entry.bind("<FocusOut>", lambda e: self._normalize_date_entry(self.end_date_var))
        end_entry.bind("<Return>", lambda e: self._normalize_date_entry(self.end_date_var))
        ttk.Button(date_frame, text="📅", width=3, command=lambda: self._open_date_picker(self.end_date_var)).pack(side=tk.LEFT, padx=(2, 0))
        
        ttk.Label(step2_frame, text="日期模式:").grid(row=3, column=0, sticky='w', pady=(10,2))
        self.date_mode_var = tk.StringVar(value="随机日期")
        self.date_mode_combo = ttk.Combobox(step2_frame, textvariable=self.date_mode_var, values=["随机日期", "连续日期"], state="readonly", width=10)
        self.date_mode_combo.grid(row=3, column=1, sticky='w', pady=2)

        ttk.Label(step2_frame, text="连续天数:").grid(row=4, column=0, sticky='w', pady=2)
        self.continuous_days_var = tk.IntVar(value=4)
        self.continuous_days_spin = ttk.Spinbox(step2_frame, from_=1, to=365, textvariable=self.continuous_days_var, width=10)
        self.continuous_days_spin.grid(row=4, column=1, sticky='w', pady=2)

        ttk.Label(step2_frame, text="随机天数(每资产):").grid(row=5, column=0, sticky='w', pady=2)
        self.random_days_var = tk.IntVar(value=10)
        self.random_days_spin = ttk.Spinbox(step2_frame, from_=1, to=365, textvariable=self.random_days_var, width=10)
        self.random_days_spin.grid(row=5, column=1, sticky='w', pady=2)

        self.unique_random_date_var = tk.BooleanVar(value=False)
        self.unique_random_cb = ttk.Checkbutton(step2_frame, text="随机日期不重复", variable=self.unique_random_date_var)
        self.unique_random_cb.grid(row=6, column=0, sticky='w', pady=(0, 4))

        self.unique_daily_var = tk.BooleanVar(value=False)
        self.unique_daily_cb = ttk.Checkbutton(step2_frame, text="同币种单日唯一", variable=self.unique_daily_var)
        self.unique_daily_cb.grid(row=6, column=1, sticky='w', pady=(0, 4))

        self.date_mode_combo.bind("<<ComboboxSelected>>", self._on_date_mode_changed)
        
        # 时间周期
        ttk.Label(step2_frame, text="时间周期 (Timeframe):").grid(row=7, column=0, sticky='w', pady=(10,2))
        
        self.tf_container = ttk.Frame(step2_frame)
        self.tf_container.grid(row=7, column=1, sticky='w', pady=2)
        
        self.timeframe_var = tk.StringVar(value="4h")
        self.all_timeframes = ["15m", "30m", "1h", "4h", "1d"]
        self.timeframe_combo = ttk.Combobox(self.tf_container, textvariable=self.timeframe_var, values=self.all_timeframes, state="readonly", width=10)
        self.timeframe_combo.pack(side=tk.LEFT)
        
        # 多周期选择区域
        self.multi_tf_vars = {}
        self.multi_tf_frame = ttk.Frame(self.tf_container)
        for tf in self.all_timeframes:
            var = tk.BooleanVar(value=False)
            self.multi_tf_vars[tf] = var
            cb = ttk.Checkbutton(self.multi_tf_frame, text=tf, variable=var)
            cb.pack(side=tk.LEFT, padx=2)
            
        # 多周期开关
        self.is_multi_tf = tk.BooleanVar(value=False)
        self.multi_tf_check = ttk.Checkbutton(step2_frame, text="多周期", variable=self.is_multi_tf, command=self._on_tf_mode_changed)
        self.multi_tf_check.grid(row=7, column=2, sticky='w', padx=5)

        ttk.Label(step2_frame, text="时间模式:").grid(row=8, column=0, sticky='w', pady=(10,2))
        self.time_mode_var = tk.StringVar(value="随机时间")
        self.time_mode_combo = ttk.Combobox(step2_frame, textvariable=self.time_mode_var, values=["随机时间", "固定时间", "连续周期"], state="readonly", width=10)
        self.time_mode_combo.grid(row=8, column=1, sticky='w', pady=2)
        self.time_mode_combo.bind("<<ComboboxSelected>>", self._on_time_mode_changed)

        self.fixed_times_label = ttk.Label(step2_frame, text="固定时间(HH:MM，逗号分隔):", font=("Arial", 8))
        self.fixed_times_label.grid(row=9, column=0, columnspan=2, sticky='w', pady=(5,2))
        self.fixed_times_var = tk.StringVar(value="03:55,15:55")
        self.fixed_times_entry = ttk.Entry(step2_frame, textvariable=self.fixed_times_var, width=20)
        self.fixed_times_entry.grid(row=10, column=0, columnspan=2, sticky='w')

        ttk.Label(step2_frame, text="资产模式:").grid(row=11, column=0, sticky='w', pady=(10,2))
        self.asset_mode_var = tk.StringVar(value="随机资产")
        self.asset_mode_combo = ttk.Combobox(step2_frame, textvariable=self.asset_mode_var, values=["随机资产", "手动资产"], state="readonly", width=10)
        self.asset_mode_combo.grid(row=11, column=1, sticky='w', pady=2)

        ttk.Label(step2_frame, text="手动资产(逗号分隔):", font=("Arial", 8)).grid(row=12, column=0, columnspan=2, sticky='w', pady=(5,2))
        self.manual_assets_var = tk.StringVar()
        ttk.Entry(step2_frame, textvariable=self.manual_assets_var, width=25).grid(row=13, column=0, columnspan=2, sticky='w')

        # 其他固定参数
        ttk.Label(step2_frame, text="Kline Count:", font=("Arial", 8)).grid(row=14, column=0, sticky='w', pady=(10,2))
        self.kline_count_var = tk.IntVar(value=40)
        ttk.Entry(step2_frame, textvariable=self.kline_count_var, width=10).grid(row=14, column=1, sticky='w')

        ttk.Label(step2_frame, text="Future Kline:", font=("Arial", 8)).grid(row=16, column=0, sticky='w', pady=2)
        self.future_kline_var = tk.IntVar(value=13)
        ttk.Entry(step2_frame, textvariable=self.future_kline_var, width=10).grid(row=16, column=1, sticky='w')

        # 连续周期设置
        self.cycle_count_label = ttk.Label(step2_frame, text="任务总数:", font=("Arial", 8))
        self.cycle_count_label.grid(row=17, column=0, sticky='w', pady=(10,2))
        self.cycle_count_var = tk.IntVar(value=10)
        self.cycle_count_spin = ttk.Spinbox(step2_frame, from_=1, to=10000, textvariable=self.cycle_count_var, width=10)
        self.cycle_count_spin.grid(row=17, column=1, sticky='w', pady=2)

        self.skip_interval_label = ttk.Label(step2_frame, text="跳过间隔(0=不跳过):", font=("Arial", 8))
        self.skip_interval_label.grid(row=18, column=0, sticky='w', pady=2)
        self.skip_interval_var = tk.IntVar(value=0)
        self.skip_interval_spin = ttk.Spinbox(step2_frame, from_=0, to=100, textvariable=self.skip_interval_var, width=10)
        self.skip_interval_spin.grid(row=18, column=1, sticky='w', pady=2)

        self._on_date_mode_changed()
        self._on_time_mode_changed()

        # 3. 操作按钮
        btn_frame = ttk.Frame(left_scrollable)
        btn_frame.pack(fill=tk.X, pady=20)
        
        # 配置网格列权重，使按钮均匀分布
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)

        ttk.Button(btn_frame, text="一键生成预览", command=self.generate_tasks).grid(row=0, column=0, padx=2, pady=5, sticky='ew')
        self.btn_verify = ttk.Button(btn_frame, text="验证所有任务", command=self.verify_tasks)
        self.btn_verify.grid(row=0, column=1, padx=2, pady=5, sticky='ew')
        
        ttk.Button(btn_frame, text="删除无效任务", command=self.delete_invalid_tasks).grid(row=1, column=0, padx=2, pady=5, sticky='ew')
        ttk.Button(btn_frame, text="清空预览", command=self.clear_tasks).grid(row=1, column=1, padx=2, pady=5, sticky='ew')

        # 4. 保存设置
        save_frame = ttk.LabelFrame(left_scrollable, text="4. 结果输出", padding=10)
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
        cols = ("task_id", "asset", "timeframe", "end_date", "end_time", "kline_count", "future_kline_count", "data_method", "status")
        self.tree = ttk.Treeview(right_frame, columns=cols, show='headings', height=25)
        
        # 设置列宽
        col_widths = {
            "task_id": 50, "asset": 80, "timeframe": 60, "end_date": 90, 
            "end_time": 70, "kline_count": 60, "future_kline_count": 60,
            "data_method": 70, "status": 80
        }
        
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=col_widths.get(col, 80), anchor='center')
        
        # Tag configuration for colors
        self.tree.tag_configure("valid", background="#E8F5E9") # Light Green
        self.tree.tag_configure("invalid", background="#FFEBEE") # Light Red
        self.tree.tag_configure("checking", background="#E3F2FD") # Light Blue
        
        # 滚动条
        scrollbar = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        # 调整 pack 顺序：先放置滚动条在右侧，再放置表格填满剩余空间
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _on_tf_mode_changed(self):
        if self.is_multi_tf.get():
            self.timeframe_combo.pack_forget()
            self.multi_tf_frame.pack(side=tk.LEFT)
        else:
            self.multi_tf_frame.pack_forget()
            self.timeframe_combo.pack(side=tk.LEFT)

    def _on_date_mode_changed(self, event=None):
        if getattr(self, "time_mode_var", None) and self.time_mode_var.get() == "连续周期":
            return
        mode = self.date_mode_var.get()
        if mode == "连续日期":
            self.continuous_days_spin.config(state="normal")
            self.random_days_spin.config(state="disabled")
            self.unique_random_cb.config(state="disabled")
        else:
            self.continuous_days_spin.config(state="disabled")
            self.random_days_spin.config(state="normal")
            self.unique_random_cb.config(state="normal")

    def _on_time_mode_changed(self, event=None):
        mode = self.time_mode_var.get()
        if mode == "连续周期":
            self.fixed_times_label.grid_remove()
            self.fixed_times_entry.grid_remove()
            self.cycle_count_label.grid()
            self.cycle_count_spin.grid()
            self.skip_interval_label.grid()
            self.skip_interval_spin.grid()
            self.continuous_days_spin.config(state="disabled")
            self.random_days_spin.config(state="disabled")
            self.unique_random_cb.config(state="disabled")
            self.date_mode_combo.config(state="disabled")
        elif mode == "固定时间":
            self.fixed_times_label.grid()
            self.fixed_times_entry.grid()
            self.cycle_count_label.grid_remove()
            self.cycle_count_spin.grid_remove()
            self.skip_interval_label.grid_remove()
            self.skip_interval_spin.grid_remove()
            self.date_mode_combo.config(state="readonly")
            self._on_date_mode_changed()
        else:
            self.fixed_times_label.grid_remove()
            self.fixed_times_entry.grid_remove()
            self.cycle_count_label.grid_remove()
            self.cycle_count_spin.grid_remove()
            self.skip_interval_label.grid_remove()
            self.skip_interval_spin.grid_remove()
            self.date_mode_combo.config(state="readonly")
            self._on_date_mode_changed()

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
        - 15m: xx:10-xx:14, xx:25-xx:29, xx:40-xx:44, xx:55-xx:59
        - 1d: 23:55-23:59
        """
        return random.choice(self._get_random_time_candidates(timeframe))

    def _get_random_time_candidates(self, timeframe):
        """返回 timeframe 对应的全部合法随机时间，供无重复抽样使用。"""
        # Handle multi-tf: "4h+15m" -> use smallest timeframe
        if "+" in timeframe:
            parts = timeframe.split("+")
            # Sort by duration ascending (smallest first)
            prio = {'1d':1440, '4h':240, '1h':60, '30m':30, '15m':15}
            parts.sort(key=lambda x: prio.get(x, 9999))
            base_tf = parts[0]
            return self._get_random_time_candidates(base_tf)

        if timeframe == '4h':
            hours = [23, 3, 7, 11, 15, 19]
            minute_ranges = [range(55, 60)]
        elif timeframe == '1h':
            hours = range(24)
            minute_ranges = [range(55, 60)]
        elif timeframe == '30m':
            hours = range(24)
            minute_ranges = [range(25, 30), range(55, 60)]
        elif timeframe == '15m':
            hours = range(24)
            minute_ranges = [range(10, 15), range(25, 30), range(40, 45), range(55, 60)]
        elif timeframe == '1d':
            hours = [23]
            minute_ranges = [range(55, 60)]
        else:
            hours = range(24)
            minute_ranges = [range(55, 60)]

        return [
            f"{hour:02d}:{minute:02d}"
            for hour in hours
            for minute_range in minute_ranges
            for minute in minute_range
        ]

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

    def _normalize_date_entry(self, var):
        s = var.get().strip()
        if len(s) == 6 and s.isdigit():
            yy = s[0:2]
            mm = s[2:4]
            dd = s[4:6]
            try:
                dt = datetime.strptime(f"20{yy}-{mm}-{dd}", "%Y-%m-%d")
                var.set(dt.strftime("%Y-%m-%d"))
            except:
                pass

    def _open_date_picker(self, target_var):
        current = target_var.get().strip()
        year = datetime.now().year
        month = datetime.now().month
        try:
            if current:
                dt = datetime.strptime(current, "%Y-%m-%d")
                year = dt.year
                month = dt.month
        except:
            pass

        top = tk.Toplevel(self.root)
        top.title("选择日期")
        top.grab_set()

        state = {"year": year, "month": month}

        year_var = tk.IntVar(value=year)
        month_var = tk.IntVar(value=month)

        header_frame = ttk.Frame(top)
        header_frame.pack(fill=tk.X, pady=5)

        body_frame = ttk.Frame(top)
        body_frame.pack(padx=5, pady=5)

        def render():
            for child in header_frame.winfo_children():
                child.destroy()

            for child in body_frame.winfo_children():
                child.destroy()

            y = state["year"]
            m = state["month"]

            year_var.set(y)
            month_var.set(m)

            ttk.Button(header_frame, text="<", width=3, command=prev_month).pack(side=tk.LEFT, padx=5)

            ttk.Label(header_frame, text="年").pack(side=tk.LEFT)
            ttk.Spinbox(header_frame, from_=2000, to=2100, textvariable=year_var, width=6).pack(side=tk.LEFT, padx=(2, 4))
            ttk.Label(header_frame, text="月").pack(side=tk.LEFT)
            ttk.Spinbox(header_frame, from_=1, to=12, textvariable=month_var, width=3).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Button(header_frame, text="跳转", width=4, command=jump_to).pack(side=tk.LEFT, padx=4)

            ttk.Button(header_frame, text=">", width=3, command=next_month).pack(side=tk.RIGHT, padx=5)

            weekdays = ["一", "二", "三", "四", "五", "六", "日"]
            for idx, wd in enumerate(weekdays):
                ttk.Label(body_frame, text=wd, width=3).grid(row=0, column=idx, padx=1, pady=1)

            month_days = calendar.monthcalendar(y, m)
            for r, week in enumerate(month_days, start=1):
                for c, day in enumerate(week):
                    if day == 0:
                        ttk.Label(body_frame, text="", width=3).grid(row=r, column=c, padx=1, pady=1)
                    else:
                        def select(d=day, yy=y, mm=m):
                            try:
                                dt_sel = datetime(yy, mm, d)
                                target_var.set(dt_sel.strftime("%Y-%m-%d"))
                            except:
                                pass
                            top.destroy()

                        ttk.Button(body_frame, text=str(day), width=3, command=select).grid(row=r, column=c, padx=1, pady=1)

        def prev_month():
            y = state["year"]
            m = state["month"] - 1
            if m < 1:
                m = 12
                y -= 1
            state["year"] = y
            state["month"] = m
            render()

        def next_month():
            y = state["year"]
            m = state["month"] + 1
            if m > 12:
                m = 1
                y += 1
            state["year"] = y
            state["month"] = m
            render()

        def jump_to():
            try:
                y = int(year_var.get())
                m = int(month_var.get())
                if m < 1 or m > 12:
                    return
                state["year"] = y
                state["month"] = m
                render()
            except:
                pass

        render()

    def _check_data_availability(self, asset, timeframe, end_date, end_time):
        """验证数据是否存在"""
        if not API_URL:
            return True # No API configured, skip validation
            
        symbol = asset.replace('/', '-')
        tf = timeframe.split('+')[0]
        # Ensure proper datetime format
        if len(end_time) == 5:
            dt_str = f"{end_date} {end_time}:00"
        else:
            dt_str = f"{end_date} {end_time}"
        
        try:
            url = f"{API_URL.rstrip('/')}/api/v5/market/candles"
            headers = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
            params = {
                "instId": symbol,
                "bar": tf.upper() if tf.endswith(('h','d','w','mo')) else tf,
                "limit": 1,
                "before": str(int(pd.Timestamp(dt_str).value // 1_000_000)) if dt_str else None
            }
            params = {k: v for k, v in params.items() if v is not None}
            
            # Retry logic: 3 attempts
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Increase timeout to 10 seconds
                    resp = requests.get(url, params=params, headers=headers, timeout=10)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        # Handle v5 API response: code=="0" and data has header+rows
                        if isinstance(data, dict):
                             if data.get("code") == "0" and data.get("data"):
                                 d = data["data"]
                                 if isinstance(d, list) and len(d) > 1:
                                     return True
                        elif isinstance(data, list) and len(data) > 0:
                            return True
                    elif resp.status_code == 429:
                        # Rate limit, wait a bit
                        import time
                        time.sleep(1)
                        continue
                        
                    # If we got a response but it wasn't 200 or 429, break and return False (or handle error)
                    # For now, if 404 or 500, we might want to retry 500 but not 404.
                    if resp.status_code >= 500:
                         continue
                    
                    break # Break if successful response logic processed or non-retriable error
                    
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries - 1:
                        raise e # Re-raise last exception
                    continue

            return False
        except Exception as e:
            print(f"Validation error for {symbol} at {dt_str}: {e}")
            return False

    def generate_tasks(self):
        try:
            asset_mode = getattr(self, "asset_mode_var", None)
            asset_mode_value = asset_mode.get() if asset_mode else "随机资产"
            if asset_mode_value == "随机资产" and not self.assets:
                messagebox.showwarning("警告", "请先选择有效的数据源文件")
                return

            count = self.pick_count_var.get()
            start_date = self.start_date_var.get()
            end_date = self.end_date_var.get()
            
            if self.is_multi_tf.get():
                selected = [tf for tf in self.all_timeframes if self.multi_tf_vars[tf].get()]
                if not selected:
                    messagebox.showerror("错误", "请至少选择一个时间周期")
                    return
                # Sort descending duration (Big -> Small) for string "4h+15m"
                prio = {'1d':5, '4h':4, '1h':3, '30m':2, '15m':1}
                selected.sort(key=lambda x: prio.get(x, 0), reverse=True)
                tf = "+".join(selected)
            else:
                tf = self.timeframe_var.get()

            k_count = self.kline_count_var.get()
            fut_count = self.future_kline_var.get()
            date_mode = getattr(self, "date_mode_var", None)
            date_mode_value = date_mode.get() if date_mode else "随机日期"
            time_mode = getattr(self, "time_mode_var", None)
            time_mode_value = time_mode.get() if time_mode else "随机时间"
            
            # 清空旧数据
            self.clear_tasks()
            
            # 清空文件名（确保下次保存时触发自动命名）
            self.filename_var.set("")
            
            assets_list = []
            if asset_mode_value == "手动资产":
                raw_assets = self.manual_assets_var.get().strip()
                if not raw_assets:
                    messagebox.showerror("错误", "资产模式为手动资产时，请输入资产列表")
                    return
                parts = [p.strip() for p in raw_assets.split(",") if p.strip()]
                if not parts:
                    messagebox.showerror("错误", "资产模式为手动资产时，请输入至少一个资产")
                    return
                for a in parts:
                    a = a.upper()
                    if "/" not in a and a.endswith("USDT"):
                        a = a[:-4] + "/USDT"
                    assets_list.append(a)
            else:
                if count <= len(self.assets):
                    assets_list = random.sample(self.assets, count)
                else:
                    assets_list = [random.choice(self.assets) for _ in range(count)]

            if time_mode_value == "连续周期":
                period_map = {'15m': 15, '30m': 30, '1h': 60, '4h': 240, '1d': 1440}
                if self.is_multi_tf.get():
                    selected = [t for t in self.all_timeframes if self.multi_tf_vars[t].get()]
                    if not selected:
                        messagebox.showerror("错误", "请至少选择一个时间周期")
                        return
                    base_tf = min(selected, key=lambda x: period_map.get(x, 1440))
                else:
                    base_tf = tf
                period_mins = period_map.get(base_tf, 240)
                skip = self.skip_interval_var.get()
                interval_mins = period_mins * (skip + 1)

                cycle_count = self.cycle_count_var.get()
                if cycle_count <= 0:
                    messagebox.showerror("错误", "任务总数必须大于0")
                    return

                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                except:
                    messagebox.showerror("错误", "日期格式错误，请使用 YYYY-MM-DD")
                    return

                end_boundary = end_dt.replace(hour=23, minute=59, second=59)
                current_dt = start_dt.replace(hour=0, minute=0, second=0)

                tasks = []
                task_id = 1

                for i in range(cycle_count):
                    if current_dt > end_boundary:
                        break
                    asset = assets_list[i % len(assets_list)]
                    actual_dt = current_dt - timedelta(minutes=1)
                    d = actual_dt.strftime("%Y-%m-%d")
                    t = actual_dt.strftime("%H:%M")
                    task = {
                        "task_id": task_id,
                        "asset": asset,
                        "timeframe": tf,
                        "end_date": d,
                        "end_time": t,
                        "kline_count": k_count,
                        "future_kline_count": fut_count,
                        "data_method": "to_end",
                        "status": "Pending"
                    }
                    tasks.append(task)
                    task_id += 1
                    current_dt += timedelta(minutes=interval_mins)

                tasks.sort(key=lambda x: (x["end_date"], x["end_time"], x["asset"]))
                self.generated_tasks = tasks
                for item in self.tree.get_children():
                    self.tree.delete(item)
                for task in tasks:
                    cols_order = ["task_id", "asset", "timeframe", "end_date", "end_time", "kline_count", "future_kline_count", "data_method", "status"]
                    values = [task[k] for k in cols_order]
                    self.tree.insert('', 'end', values=values)
                self.preview_info.config(text=f"预览: {len(self.generated_tasks)} 条任务")
                return

            dates_list = []
            start_dt = None
            end_dt = None
            total_days = None
            random_days = None
            use_unique_random = False
            if date_mode_value == "连续日期":
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                except:
                    messagebox.showerror("错误", "日期格式错误，请使用 YYYY-MM-DD")
                    return
                days = self.continuous_days_var.get()
                if days <= 0:
                    messagebox.showerror("错误", "连续天数必须大于 0")
                    return
                last_dt = start_dt + timedelta(days=days - 1)
                if last_dt > end_dt:
                    messagebox.showerror("错误", "连续天数超出日期范围，请调整起始日期或连续天数")
                    return
                for i in range(days):
                    d = start_dt + timedelta(days=i)
                    dates_list.append(d.strftime("%Y-%m-%d"))
            else:
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                except:
                    messagebox.showerror("错误", "日期格式错误，请使用 YYYY-MM-DD")
                    return
                if end_dt < start_dt:
                    messagebox.showerror("错误", "结束日期必须不早于开始日期")
                    return
                total_days = (end_dt - start_dt).days + 1
                random_days = self.random_days_var.get()
                if random_days <= 0:
                    messagebox.showerror("错误", "随机天数必须大于 0")
                    return
                use_unique_random = self.unique_random_date_var.get()
                if use_unique_random and random_days > total_days:
                    messagebox.showerror("错误", "随机天数超过日期范围内可用的天数")
                    return

            times_list = []
            if time_mode_value == "固定时间":
                raw_times = self.fixed_times_var.get().strip()
                # 支持中文逗号
                raw_times = raw_times.replace('，', ',')
                if not raw_times:
                    messagebox.showerror("错误", "时间模式为固定时间时，请输入至少一个时间")
                    return
                parts = [p.strip() for p in raw_times.split(",") if p.strip()]
                if not parts:
                    messagebox.showerror("错误", "时间模式为固定时间时，请输入至少一个时间")
                    return
                for t in parts:
                    if ":" not in t:
                        messagebox.showerror("错误", "固定时间格式应为 HH:MM，用逗号分隔")
                        return
                    h_str, m_str = t.split(":", 1)
                    if not (h_str.isdigit() and m_str.isdigit()):
                        messagebox.showerror("错误", "固定时间格式应为 HH:MM，用逗号分隔")
                        return
                    h = int(h_str)
                    m = int(m_str)
                    if not (0 <= h <= 23 and 0 <= m <= 59):
                        messagebox.showerror("错误", "固定时间应在 00:00 到 23:59 之间")
                        return
                    times_list.append(f"{h:02d}:{m:02d}")
            else:
                times_list.append("RANDOM")

            tasks = []
            task_id = 1
            seen_task_keys = set()
            
            # Check validation var existence safely
            should_validate = False
            if hasattr(self, 'validate_data_var') and self.validate_data_var.get():
                should_validate = True

            for asset in assets_list:
                seen_dates_for_asset = set()

                if date_mode_value == "连续日期":
                    for d in dates_list:
                        if self.unique_daily_var.get() and d in seen_dates_for_asset:
                            continue
                        
                        # 每天仍生成一个任务，但完整任务时间不得重复。
                        time_candidates = (self._get_random_time_candidates(tf)
                                           if times_list == ["RANDOM"]
                                           else list(dict.fromkeys(times_list)))
                        current_times = [t for t in time_candidates
                                         if (asset, tf, d, t) not in seen_task_keys]
                        if not current_times:
                            continue

                        for t in [random.choice(current_times)]:
                            if self.unique_daily_var.get() and d in seen_dates_for_asset:
                                continue

                            if t == "RANDOM":
                                end_time_value = self._generate_random_time(tf)
                            else:
                                end_time_value = t
                            
                            # 验证数据
                            if should_validate:
                                if not self._check_data_availability(asset, tf, d, end_time_value):
                                    print(f"Skipping invalid data: {asset} {d} {end_time_value}")
                                    continue

                            task = {
                                "task_id": task_id,
                                "asset": asset,
                                "timeframe": tf,
                                "end_date": d,
                                "end_time": end_time_value,
                                "kline_count": k_count,
                                "future_kline_count": fut_count,
                                "data_method": "to_end",
                                "status": "Pending"
                            }
                            tasks.append(task)
                            seen_task_keys.add((asset, tf, d, end_time_value))
                            task_id += 1
                            
                            if self.unique_daily_var.get():
                                seen_dates_for_asset.add(d)

                else:
                    if use_unique_random:
                        indices = random.sample(range(total_days), random_days)
                        indices.sort()
                        dates_for_asset = []
                        for idx in indices:
                            d = start_dt + timedelta(days=idx)
                            dates_for_asset.append(d.strftime("%Y-%m-%d"))
                    else:
                        dates_for_asset = []
                        for _ in range(random_days):
                            d = self._get_random_date(start_date, end_date)
                            dates_for_asset.append(d)
                    
                    for d in dates_for_asset:
                        if self.unique_daily_var.get() and d in seen_dates_for_asset:
                            continue

                        # 日期可以重复；同一日期碰撞时改抽尚未使用的时间。
                        time_candidates = (self._get_random_time_candidates(tf)
                                           if times_list == ["RANDOM"]
                                           else list(dict.fromkeys(times_list)))
                        current_times = [t for t in time_candidates
                                         if (asset, tf, d, t) not in seen_task_keys]
                        if not current_times:
                            continue

                        for t in [random.choice(current_times)]:
                            if self.unique_daily_var.get() and d in seen_dates_for_asset:
                                continue

                            if t == "RANDOM":
                                end_time_value = self._generate_random_time(tf)
                            else:
                                end_time_value = t
                            
                            task = {
                                "task_id": task_id,
                                "asset": asset,
                                "timeframe": tf,
                                "end_date": d,
                                "end_time": end_time_value,
                                "kline_count": k_count,
                                "future_kline_count": fut_count,
                                "data_method": "to_end",
                                "status": "Pending"
                            }
                            tasks.append(task)
                            seen_task_keys.add((asset, tf, d, end_time_value))
                            task_id += 1

                            if self.unique_daily_var.get():
                                seen_dates_for_asset.add(d)

            tasks.sort(key=lambda x: (x["end_date"], x["end_time"], x["asset"]))

            self.generated_tasks = []
            for item in self.tree.get_children():
                self.tree.delete(item)

            self.generated_tasks = tasks
            for task in tasks:
                cols_order = ["task_id", "asset", "timeframe", "end_date", "end_time", "kline_count", "future_kline_count", "data_method", "status"]
                values = [task[k] for k in cols_order]
                self.tree.insert('', 'end', values=values)

            self.preview_info.config(text=f"预览: {len(self.generated_tasks)} 条任务")
        except Exception as e:
            messagebox.showerror("生成失败", str(e))

    def verify_tasks(self):
        """启动后台线程验证任务"""
        if not self.generated_tasks:
            messagebox.showwarning("警告", "没有可验证的任务")
            return
            
        self.btn_verify.config(state="disabled", text="验证中...")
        
        # 收集数据以免在多线程中访问Tkinter控件
        items = self.tree.get_children()
        tasks_data = []
        for i, item_id in enumerate(items):
            values = self.tree.item(item_id, 'values')
            tasks_data.append((i, item_id, values))
            self.tree.item(item_id, tags=('checking',))
            
        t = threading.Thread(target=self._run_verification, args=(tasks_data,))
        t.daemon = True
        t.start()

    def _run_verification(self, tasks_data):
        """后台验证循环 (并行版)"""
        total = len(tasks_data)
        completed_count = 0
        
        def verify_single(idx, item_id, values):
            try:
                # cols: task_id, asset, timeframe, end_date, end_time, ...
                asset = values[1]
                tf = values[2]
                end_date = values[3]
                end_time = values[4]
                
                is_valid = self._check_data_availability(asset, tf, end_date, end_time)
                return idx, item_id, values, is_valid
            except Exception as e:
                print(f"Error checking {values}: {e}")
                return idx, item_id, values, False

        # 默认并发数 6
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(verify_single, i, item_id, vals) for i, item_id, vals in tasks_data]
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    idx, item_id, values, is_valid = future.result()
                    completed_count += 1
                    
                    status_text = "Valid" if is_valid else "Invalid"
                    tag = "valid" if is_valid else "invalid"
                    
                    def update_ui(iid=item_id, s=status_text, t=tag, v=values, ix=idx):
                        if not self.tree.exists(iid):
                            return
                            
                        # 更新 TreeView
                        curr_vals = list(self.tree.item(iid, 'values'))
                        if not curr_vals: 
                            curr_vals = list(v)
                            
                        if len(curr_vals) >= 9:
                            curr_vals[8] = s
                        else:
                            curr_vals.append(s)
                            
                        self.tree.item(iid, values=curr_vals, tags=(t,))
                        self.preview_info.config(text=f"验证进度: {completed_count}/{total}")
                        
                        # 更新内存数据
                        if ix < len(self.generated_tasks):
                            task = self.generated_tasks[ix]
                            # 校验 task_id 以确保对应正确
                            if str(task.get("task_id")) == str(curr_vals[0]):
                                task["status"] = s

                    self.root.after(0, update_ui)
                    
                except Exception as e:
                    print(f"Error getting future result: {e}")

        self.root.after(0, lambda: self.btn_verify.config(state="normal", text="验证所有任务"))
        self.root.after(0, lambda: self.preview_info.config(text=f"预览: {total} 条任务 (验证完成)"))

    def delete_invalid_tasks(self):
        """删除状态为 Invalid 的任务"""
        if not self.generated_tasks:
            return
            
        original_count = len(self.generated_tasks)
        # Filter out invalid tasks
        self.generated_tasks = [t for t in self.generated_tasks if t.get("status") != "Invalid"]
        new_count = len(self.generated_tasks)
        
        deleted_count = original_count - new_count
        
        # Refresh Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        for task in self.generated_tasks:
            cols_order = ["task_id", "asset", "timeframe", "end_date", "end_time", "kline_count", "future_kline_count", "data_method", "status"]
            values = [task[k] for k in cols_order]
            
            # Restore tag based on status
            tag = "valid" if task.get("status") == "Valid" else ""
            if task.get("status") == "Pending": tag = ""
            
            self.tree.insert('', 'end', values=values, tags=(tag,))
            
        self.preview_info.config(text=f"预览: {new_count} 条任务")
        if deleted_count > 0:
            messagebox.showinfo("完成", f"已删除 {deleted_count} 条无效任务")
        else:
            messagebox.showinfo("提示", "没有发现无效任务")


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
            cols_order = ["task_id", "asset", "timeframe", "end_date", "end_time", "kline_count", "future_kline_count", "data_method"]
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
