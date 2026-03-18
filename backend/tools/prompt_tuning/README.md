# Decision Agent Prompt Tuning Lab

这是一个面向 `Decision Agent` 的本地 Prompt 调优工具，当前支持三种模式：

- 单个 JSON 调试
- 文件夹批量回测
- 自动化优化 `Auto-Optimizer`

当前版本重点解决三类问题：

1. 快速人工调 Prompt
2. 用一批历史 JSON 做批量回测，比较不同 Prompt 的效果
3. 让 Optimizer LLM 基于历史表现自动迭代生成下一版 Prompt

## 目录结构

```text
backend/tools/prompt_tuning/
├── local_gui.py                 # GUI 入口
├── prompt_tuning_engine.py      # 核心执行层：加载、调用、回测、导出
├── auto_optimizer.py            # 自动优化主循环
├── test_prompt.py               # 命令行单文件测试
├── extract_context.py           # 提取精简上下文
├── test_prompt_tuning_engine.py # Prompt tuning 核心测试
├── test_auto_optimizer.py       # Auto-Optimizer 测试
├── test_llm_compat.py           # LLM 兼容层测试
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

### 3. 自动化优化模式

适合让大模型自动迭代 Prompt：

- 以当前 Prompt 为第 1 代或续跑起点
- 每一代先做整批回测
- 记录 K1 / K2 / Parse Rate / L/S Ratio 等指标
- 把历史表现喂给 Optimizer LLM
- 自动生成下一版 Prompt
- 支持连续多代运行
- 支持把最佳 Prompt 与当前 Prompt 保存到工作目录

## K1 / K2 定义

这是当前工具最重要的评估口径：

- `K1 Win Rate`
  - 价格基点后的第 `1` 根同周期 K 线命中率
- `K2 Win Rate`
  - 价格基点后的第 `2` 根同周期 K 线命中率

示例：

- 如果当前周期是 `15m`
  - `K1` = 价格基点后的第 1 根 `15m` K 线
  - `K2` = 价格基点后的第 2 根 `15m` K 线
- 如果当前周期是 `4h`
  - `K1` = 价格基点后的第 1 根 `4h` K 线
  - `K2` = 价格基点后的第 2 根 `4h` K 线

当前项目约定：

- `K1` 是主指标
- `K2` 是次指标
- `Parse Rate` 是输出稳定性指标
- `L/S Ratio` 是多空偏置健康度指标

## 回测规则

当前版本只做基础验证，不扩展复杂交易逻辑：

- 仅使用 `future_kline_data` 的前两根 K 线
- `LONG`
  - `K1`: 第 1 根未来 K 线 `close > latest_price` 记为 `win`
  - `K2`: 第 2 根未来 K 线 `close > latest_price` 记为 `win`
- `SHORT`
  - `K1`: 第 1 根未来 K 线 `close < latest_price` 记为 `win`
  - `K2`: 第 2 根未来 K 线 `close < latest_price` 记为 `win`
- `HOLD`
  - 记为 `hold`
- 缺少未来数据时
  - 记为 `backtest_skipped`

## Prompt 渲染规则

当前 Prompt 渲染已针对优化器生成的新模板做过兼容增强：

- 只替换以下占位符：
  - `{stock_name}`
  - `{time_frame}`
  - `{price_summary}`
  - `{price_info_str}`
  - `{latest_price_str}`
  - `{indicator_report}`
  - `{pattern_report}`
  - `{trend_report}`
- 其他花括号保持原样

这意味着：

- 原始模板中使用的 `{{ ... }}` JSON 示例仍然可用
- 优化器新生成的普通 JSON `{ ... }` 也不会再被误判成 `str.format(...)` 占位符

## LLM 调用兼容层

当前项目额外做了一层 LLM 兼容处理，用于适配不同供应商和返回形态：

- 统一提取纯文本响应
- 兼容：
  - `response.content` 为字符串
  - `response.content` 为内容块列表
  - 直接返回字符串
- 对已知的 `model_dump` 兼容问题做重试处理

相关实现位于：

- `backend/app/utils/llm_compat.py`

## Auto-Optimizer 的工作方式

### 评估优先级

Optimizer 当前明确按这套优先级理解历史结果：

1. 优先提高 `K1 Win Rate`
2. 在不明显伤害 `K1` 的前提下提高 `K2 Win Rate`
3. 保持 `Parse Rate = 100%`
4. 避免 `LONG / SHORT` 极端偏置

### 历史记录

工作目录中会记录：

- `optimization_history.json`
- `current_prompt.txt`
- `best_prompt_gen_X.txt`
- `gen_X/` 每一代对应的批量导出目录

### 流式生成

为避免供应商网关对长时间无响应请求做 `60s` 左右的 `504` 超时，Optimizer LLM 已改成简化流式模式：

- 后端通过 `stream(...)` 获取 chunk
- 后端将 chunk 拼成完整文本
- 最终仍按 `<prompt>...</prompt>` 解析
- GUI 只显示轻量状态，不逐 token 刷新

当前 GUI 会显示：

- Optimizer 已开始流式生成
- 已收到首个流式分块
- 流式生成完成

## 导出结果

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

## 启动方式

在项目根目录执行：

```bash
python backend/tools/prompt_tuning/local_gui.py
```

Windows PowerShell 也可以直接执行：

```powershell
python "c:/Users/gcb/Desktop/9gggggv2x5z8qm6n1p8r3b/backend/tools/prompt_tuning/local_gui.py"
```

## GUI 使用说明

### 顶部模式切换

- 点击 `单个 JSON`
  - 立即弹出文件选择框
- 点击 `文件夹批量回测`
  - 立即弹出文件夹选择框
- 点击 `自动化优化 (Auto-Optimizer)`
  - 立即弹出历史数据集文件夹选择框

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

### 自动化优化模式

自动化优化模式下可见按钮：

- `选择历史数据集文件夹`
- `选择工作目录(保存Prompt)`
- `启动自动优化`
- `取消自动优化`

流程：

1. 选择历史数据集文件夹
2. 选择工作目录
3. 设置并发数
4. 设置世代数
5. 点击 `启动自动优化`
6. 在右下区域查看：
   - 每代当前 Prompt 摘要
   - 每代详细统计
   - 流式生成状态
   - 新 Prompt 预览
   - 新 Prompt 生成理由预览

## 输出与日志说明

当前 GUI 的 `输出与日志` 面板已增强为调试型日志区：

- 每行附带时间戳
- 单文件模式会输出：
  - 状态
  - 决策
  - 解析模式
  - K1 / K2 回测结果
  - 原始 LLM 输出
- 批量模式会输出：
  - 每个文件的处理结果
  - 批量汇总
  - 导出路径
- 自动优化模式会输出：
  - 当前世代 Prompt 摘要
  - `K1 Win Rate`
  - `K2 Win Rate`
  - `Parse Rate`
  - `L/S Ratio`
  - `Execution Failures`
  - 新 Prompt 摘要
  - 流式生成状态

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

### 自动优化

```bash
python backend/tools/prompt_tuning/auto_optimizer.py --data-dir backend/data/history --work-dir backend/tools/prompt_tuning/optimization_logs --generations 5 --concurrency 3
```

## 稳定性设计

当前 GUI 与优化器做了这些稳定性处理：

- 后台线程不直接操作 `tkinter` 控件
- 所有 UI 更新通过事件队列回到主线程执行
- 每个批量任务中的文件独立捕获异常
- 单文件失败不会拖垮整个批次
- 关闭窗口时会先请求取消，再等待后台线程安全退出
- Optimizer 使用流式生成，降低长思考模型因上游 `60s` 空闲超时导致的 `504`

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

运行核心测试：

```bash
python -m unittest backend.tools.prompt_tuning.test_llm_compat backend.tools.prompt_tuning.test_auto_optimizer backend.tools.prompt_tuning.test_prompt_tuning_engine backend.tools.prompt_tuning.test_prompt
```

当前测试覆盖：

- 上下文提取
- LLM 输出 JSON 解析
- K1 / K2 回测逻辑
- 批量导出
- 坏文件隔离
- 取消后停止继续提交新任务
- Prompt 模板 JSON 花括号兼容
- LLM 兼容层
- Auto-Optimizer 事件与回退逻辑
- Auto-Optimizer 流式生成

## 注意事项

- 批量模式默认只扫描当前目录，不递归子目录
- 如果模型供应商有限流，建议先用较低并发，例如 `2` 或 `3`
- 如果 Optimizer 使用长思考模型，优先使用当前内置的流式生成方式
- 当前回测只是 Prompt 调优辅助，不代表真实交易收益
- 实际交易还会受到滑点、手续费、成交条件等影响
