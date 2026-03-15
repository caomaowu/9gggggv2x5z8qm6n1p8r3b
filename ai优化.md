# AI 决策智能体自进化系统方案 (AI Evolution Lab)

## 1. 目标
构建一套全自动化的闭环系统，利用无限的 LLM 算力，自动优化 `Decision Agent` 的 Prompt（提示词），以提高加密货币交易的方向预测准确率。

## 2. 核心架构

### 2.1 模块解耦 (Decoupling)
- **现状**: Prompt 硬编码在 `decision_agent_original.py` 中。
- **改造**:
    - 创建 `backend/app/prompts/decision_agent.json`。
    - 修改 Agent 代码，使其每次运行时从 JSON 读取 Prompt。
    - **优势**: 优化程序可以直接修改 JSON 文件来改变 Agent 行为，无需重启服务或修改代码逻辑。

### 2.2 数据采集 (Data Harvesting)
- **机制**: "黑匣子"记录模式。
- **触发**: 每次 `Decision Agent` 做出决策时。
- **记录内容**:
    - `Input`: 技术指标报告、形态识别报告、趋势分析报告。
    - `Output`: AI 的决策 (LONG/SHORT/HOLD) 及理由。
    - `Context`: 当时的 K 线数据（用于验证未来走势）。
    - `Prompt`: 当时使用的 Prompt 版本。
- **存储**: `data/optimization/training_samples.jsonl`

### 2.3 黄金数据集 (Golden Dataset)
- **定义**: 一组包含 150个历史行情的标准化测试集。
- **来源**: 从回测工具生成，文件名为 `golden_dataset.csv`。在 tools\golden_dataset.csv
- **作用**: 作为"考卷"，用于评估每个新版本 Prompt 的得分。

### 2.4 进化引擎 (Evolution Engine)
这是一个独立的 Python 脚本 (`tools/optimizer.py`)，执行以下无限循环：

1.  **Run (考试)**: 使用当前 Prompt 跑一遍"黄金数据集"。
2.  **Evaluate (评分)**: 统计胜率、盈亏比。如果分数创新高，保存该版本。
3.  **Diagnose (诊断)**: 找出亏损的案例（错题集）。
4.  **Mutate (变异)**:
    - 将"错题集" + "当前 Prompt" 发送给 Teacher LLM (最强模型)。
    - 指令: "你的学生在这些案例中犯了错（做多跌了，做空涨了）。请分析原因，并修改 Prompt 中的决策逻辑（如权重分配、风险控制），以修正这些错误，同时不要破坏原有的正确逻辑。"
5.  **Update (更新)**: 将 Teacher LLM 生成的新 Prompt 写入 JSON 文件，进入下一轮循环。

## 3. 执行计划

### 第一阶段：基础设施 (Infrastructure)
1.  **Prompt 提取**: 将 `decision_agent_original.py` 中的 Prompt 移至外部 JSON。
2.  **埋点系统**: 在 Agent 中添加日志代码，将每次决策的输入输出保存到 `data/optimization/` 目录。
3.  **数据集构建**: 使用回测工具生成150个 BTC/ETH/SOL 的 4h历史任务，作为基准测试集。（已经存在）

### 第二阶段：进化循环 (Evolution Loop)
1.  **编写 Optimizer**: 开发自动运行回测、统计结果、调用 LLM 修改 Prompt 的脚本。
2.  **自动评估**: 实现一个打分函数（Score = WinRate * 0.4 + PnL_Ratio * 0.6）。

## 4. 数据结构示例

### 训练样本 (Sample)
```json
{
  "task_id": "job-20240301-btc",
  "timestamp": "2024-03-01T12:00:00",
  "inputs": {
    "indicator": "RSI(75) Overbought, MACD Bullish...",
    "pattern": "Double Top detected...",
    "trend": "Hitting Resistance at 65000..."
  },
  "agent_output": {
    "decision": "LONG",
    "reasoning": "Momentum is strong..."
  },
  "ground_truth": {
    "outcome": "LOSS",
    "actual_move": "-2.5% in 4h"
  }
}
```

## 5. 预期成果
- 获得一套能够自我迭代的 Prompt 体系。
- 发现人类难以察觉的 Prompt 优化点（例如："在 RSI>80 时，忽略所有形态信号，强制做空"）。
- 最终输出一个经过成百上千次实战模拟验证的"超级决策 Prompt"。
