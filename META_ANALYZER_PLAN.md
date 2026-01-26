# QuantAgent Meta-Analyzer (元分析系统) 设计方案

## 1. 项目背景与目标

当前 `batch_backtest_app` 已经能够高效地执行批量回测并生成统计结果（CSV），且 `backend/data/history/` 目录完整保存了每次分析的详细上下文（JSON），包括决策逻辑、指标报告、形态报告、趋势报告以及当时的未来 K 线数据。

**目标**：构建一个“元分析系统” (Meta-Analyzer)，利用上述数据进行**二次分析**。它不直接进行交易，而是充当“AI 交易教练”，通过复盘历史案例，自动诊断 Agent 的决策缺陷，并提供具体的优化建议（如 Prompt 调整、权重参数修正），从而实现系统的“自我进化”。

## 2. 核心架构设计

系统采用 **ETL-RAG-Analysis** 架构，分为数据层、诊断层和优化层。

### 2.1 数据层 (Data Layer) - ETL
负责将零散的回测结果与详细的上下文数据关联起来。

*   **输入源**:
    1.  **统计索引**: `tools/backtest_results.csv` (包含 result_id, 盈亏结果, 时间, 资产)。注意：如果文件不存在，需提示用户运行回测或仅支持手动加载 JSON。
    2.  **上下文详情**: `backend/data/history/YYYY-MM-DD/{result_id}.json` (包含完整的 Agent 思维链、技术指标数据、未来K线验证数据)。
*   **功能**:
    *   **Data Loader**: 解析 CSV，提取高价值案例（如：大亏、大赚、踏空）。
    *   **Context Fetcher**: 根据 result_id 自动定位并加载对应的 JSON 文件。
    *   **Data Validation**: 检查 JSON 中是否包含必要的 `future_kline_data` (或 `future_kline`) 数据用于复盘验证。

### 2.2 诊断层 (Diagnosis Layer) - Meta-Agent
利用大模型（由用户决定配置）扮演“复盘专家”。

*   **输入**:
    *   **原始决策**: Agent 当时的分析报告（指标、形态、趋势、最终决策）。
    *   **上帝视角**: 随后发生的真实 K 线走势（Future Data）。
*   **Prompt 策略**:
    *   **角色**: "你是一位无情的量化交易审计员。"
    *   **任务**: "对比 Agent 的预测与实际市场走势，找出逻辑漏洞。"
    *   **输出结构**:
        1.  **归因 (Attribution)**: 错误原因（数据噪音 / 逻辑谬误 / 模型幻觉 / 风险控制缺失）。
        2.  **关键缺失 (Missing Link)**: Agent 漏看了什么信号（如：忽视了 4H 级别的顶背离）。
        3.  **评分 (Score)**: 对 Agent 当次表现打分 (0-100)。

### 2.3 优化层 (Optimization Layer) - Evolution
基于诊断结果生成可执行的优化建议。

*   **聚合分析 (Aggregator)**:
    *   统计错误模式分布（例如：80% 的亏损是因为抄底过早）。
*   **进化顾问 (Advisor)**:
    *   **Prompt Patching**: 针对性修改 System Prompt（例如：“建议在 Decision Agent 的 Prompt 中增加‘必须等待突破确认’的指令”）。
    *   **Config Tuning**: 调整参数（例如：“建议将 `RISK_REWARD_RATIO` 从 1.5 提高到 2.0”）。

## 3. 功能模块与目录结构

建议在 `tools/` 下新建 `meta_analyzer` 模块：

```text
refactor_v2/
├── tools/
│   ├── meta_analyzer/
│   │   ├── __init__.py
│   │   ├── app.py              # Streamlit Web UI 入口
│   │   ├── loader.py           # 数据加载与关联模块
│   │   ├── diagnosis.py        # 诊断 Agent 核心逻辑
│   │   ├── aggregator.py       # 统计分析与建议生成
│   │   └── templates/          # 诊断专用 Prompt 模板
│   │       ├── critic_prompt.md    # 批评家 Prompt
│   │       └── advisor_prompt.md   # 顾问 Prompt
```

## 4. 用户界面 (Streamlit UI)

设计一个交互式的复盘控制台：

1.  **侧边栏 (Sidebar)**:
    *   **过滤器**: 按 资产 / 时间 / 盈亏结果 / 策略版本 筛选案例。
    *   **快捷按钮**: “加载大亏案例”、“加载踏空案例”。
2.  **主视图 (Main View)**:
    *   **案例详情**: 左侧展示 Agent 原始分析，右侧展示实际走势图（标注买卖点）。
    *   **AI 诊断报告**: 动态生成的复盘分析文本。
    *   **全局洞察**: 统计图表（错误类型饼图、改进建议列表）。

## 5. 开发路线图 (Roadmap)

1.  **Step 1: 原型搭建 (Prototype)**
    *   创建 `loader.py`，实现 CSV 与 JSON 的关联读取。
    *   搭建基础 Streamlit 界面，展示历史回测数据的列表与详情。
2.  **Step 2: 诊断逻辑 (Diagnosis Logic)**
    *   集成 LLM（需参考 `batch_backtest_app` 实现独立的 Client，或复用 `backend/app/core` 配置），实现单案例的 AI 复盘功能。
    *   **Prompt Engineering**: 编写并优化 `critic_prompt.md`。
3.  **Step 3: 批量分析 (Batch Analysis)**
    *   实现对筛选出的数据集进行批量诊断，生成汇总报告。
4.  **Step 4: 建议生成 (Advisory)**
    *   根据汇总数据，生成具体的代码或配置修改建议。

## 6. 前置条件检查

*   **数据完整性**: 确保 `batch_backtest_app` 运行时开启了 `future_kline_count`，否则 JSON 中缺乏用于验证的未来数据，Meta-Analyzer 需要自行重新拉取行情。
*   **API 成本**: 批量诊断会消耗大量 Token，需提供成本估算或限制分析数量的功能。
