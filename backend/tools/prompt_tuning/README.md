# Decision Agent Prompt Tuning Lab

这是一个面向 `Decision Agent` 的本地 Prompt 调优工具，支持：

- 单个 JSON 调试
- 文件夹批量回测
- 多线程并发执行
- 批量结果导出
- K1 / K2 基础回测验证

当前版本重点解决两类问题：

1. 快速人工调 Prompt
2. 用一批历史 JSON 做批量回测，比较不同 Prompt 的效果

## 目录结构

```text
backend/tools/prompt_tuning/
├── local_gui.py                 # GUI 入口
├── prompt_tuning_engine.py      # 核心执行层：加载、调用、回测、导出
├── test_prompt.py               # 命令行单文件测试
├── extract_context.py           # 提取精简上下文
├── test_prompt_tuning_engine.py # 单元测试
└── README.md
```

## 功能概览

### 1. 单个 JSON 模式

适合做交互式调试：

- 加载一个历史 JSON
- 编辑 Prompt 模板
- 调用 LLM
- 查看原始输出
- 自动做 K1 / K2 回测验证

### 2. 文件夹批量回测模式

适合做 Prompt 对比和批量复盘：

- 选择一个文件夹
- 非递归扫描当前目录下的 `*.json`
- 可配置并发数，范围 `1-8`
- 每个文件独立运行，单文件失败不会中断整批
- 支持取消任务
- 批量结束后自动导出结果

### 3. 导出结果

批量运行后固定导出两份文件：

- `batch_results.json`
- `batch_results.csv`

导出内容包含：

- 运行配置
- 汇总统计
- 每个 JSON 的结构化结果
- K1 / K2 的价格、涨跌幅、胜负结果

默认不导出：

- 原始 Prompt 全文
- 原始 LLM 回复全文

但会记录：

- `prompt_sha256`

用于追踪当前批次实际使用的 Prompt 内容版本。

## 回测规则

当前版本只做基础验证，不扩展复杂交易逻辑：

- 仅使用 `future_kline_data` 的前两根 K 线
- `LONG`
  - 下一根或下两根 `close > latest_price` 记为 `win`
- `SHORT`
  - 下一根或下两根 `close < latest_price` 记为 `win`
- `HOLD`
  - 记为 `hold`
- 缺少未来数据时
  - 记为 `backtest_skipped`

## 启动方式

在项目根目录执行：

```bash
python backend/tools/prompt_tuning/local_gui.py
```

Windows PowerShell 也可以直接执行：

```powershell
python "c:/Users/11618/Desktop/refactor_v2(1)(1)(2)/backend/tools/prompt_tuning/local_gui.py"
```

## GUI 使用说明

### 顶部模式切换

- 点击 `单个 JSON`
  - 立即弹出文件选择框
- 点击 `文件夹批量回测`
  - 立即弹出文件夹选择框

### 单个模式

单个模式下可见按钮：

- `重新选择 JSON`
- `运行单个测试`

流程：

1. 选择一个历史 JSON
2. 修改左侧 Prompt 模板
3. 点击 `运行单个测试`
4. 在右下区域查看：
   - LLM 原始输出
   - 决策解析结果
   - K1 / K2 回测结果

### 批量模式

批量模式下可见按钮：

- `重新选择文件夹`
- `选择导出目录`
- `启动批量回测`
- `取消批量任务`

流程：

1. 选择包含历史 JSON 的文件夹
2. 设置并发数
3. 选择导出目录
4. 修改左侧 Prompt 模板
5. 点击 `启动批量回测`
6. 在右下区域查看实时日志和统计
7. 批量结束后到导出目录查看结果文件

## 命令行工具

### 单文件测试

```bash
python backend/tools/prompt_tuning/test_prompt.py --context backend/data/history/xxx.json --version original
```

可选版本：

- `original`
- `lite`

### 提取上下文

```bash
python backend/tools/prompt_tuning/extract_context.py --input backend/data/history/xxx.json --output extracted_context.json
```

## 稳定性设计

当前 GUI 做了以下稳定性处理：

- 后台线程不直接操作 `tkinter` 控件
- 所有 UI 更新通过事件队列回到主线程执行
- 每个批量任务中的文件独立捕获异常
- 单文件失败不会拖垮整个批次
- 关闭窗口时会先请求取消，再等待后台线程安全退出

## 依赖与前置条件

需要：

- Python
- `tkinter`
- `.env` 已配置在 `backend/.env`
- 已安装项目依赖

安装依赖：

```bash
pip install -r requirements.txt
```

## 测试

运行单元测试：

```bash
python -m unittest backend/tools/prompt_tuning/test_prompt_tuning_engine.py
```

当前测试覆盖：

- 上下文提取
- LLM 输出 JSON 解析
- K1 / K2 回测逻辑
- 批量导出
- 坏文件隔离
- 取消后停止继续提交新任务

## 注意事项

- 批量模式默认只扫描当前目录，不递归子目录
- 如果模型供应商有限流，建议先用较低并发，例如 `2` 或 `3`
- 当前回测只是 Prompt 调优辅助，不代表真实交易收益
- 实际交易还会受到滑点、手续费、成交条件等影响
