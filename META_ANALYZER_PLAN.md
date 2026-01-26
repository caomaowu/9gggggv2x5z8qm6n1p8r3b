# QuantAgent Meta-Analyzer (元分析系统) 设计方案

## 1. 项目背景与目标

当前 `batch_backtest_app` 已经能够高效地执行批量回测并生成统计结果（CSV），且 `backend/data/history/` 目录完整保存了每次分析的详细上下文（JSON），包括决策逻辑、指标报告、形态报告以及当时的未来 K 线数据。

**目标**：构建一个“元分析系统” (Meta-Analyzer)，利用上述数据进行**二次分析**。它不直接进行交易，而是充当“AI 交易教练”，通过复盘历史案例，自动诊断 Agent 的决策缺陷，并提供具体的优化建议（如 Prompt 调整、权重参数修正），从而实现系统的“自我进化”。

---

## 2. 系统架构

本系统作为一个独立的工具模块存在，不干扰核心交易系统的运行。

### 2.1 目录结构
建议在 `tools/` 目录下创建独立模块：

```text
tools/meta_analyzer/
├── analyzer.py           # 核心分析引擎
├── case_filter.py        # 案例筛选器 (筛选典型失败/成功案例)
├── llm_judge.py          # LLM 诊断模块 (Prompt 工程)
├── report_generator.py   # 报告生成器 (Markdown/HTML)
└── templates/            # 报告模板
```

### 2.2 数据流向

1.  **输入层**:
    *   **量化结果**: 读取 `batch_backtest_app` 生成的 CSV 文件（获取宏观胜率、盈亏比）。
    *   **详细案卷**: 读取 `backend/data/history/YYYY-MM-DD/*.json`（获取微观的 Reasoning、Context、Future Kline）。

2.  **处理层**:
    *   **Step 1 样本筛选**: 自动挑选具有“复盘价值”的案例。
        *   *Type A (惨痛教训)*: 信心分 (Confidence) 高，但实际走势相反。
        *   *Type B (踏空遗憾)*: 决策为 HOLD/SHORT，但实际大幅上涨。
        *   *Type C (精准捕获)*: 决策正确且收益极高的案例（用于提取成功模式）。
    *   **Step 2 深度诊断 (LLM Judge)**:
        *   将当时的 **Input** (指标/形态/趋势报告) + **Output** (决策逻辑) + **Ground Truth** (未来实际 K 线) 投喂给高智商模型 (如 DeepSeek/GPT-4)。
        *   **提问**: "Agent 当时认为要做空，理由是 RSI 超买。但实际上价格继续暴涨。请分析是哪个指标产生了误导？是形态识别错误，还是对趋势的权重判断不足？"

3.  **输出层**:
    *   **进化报告**: 生成包含统计图表和文字建议的 Markdown 报告。
    *   **Prompt 补丁**: 针对发现的共性问题，自动生成 System Prompt 的优化建议片段。

---

## 3. 核心功能模块详解

### 3.1 归因分析 (Root Cause Analysis)
LLM Judge 将把错误案例归类为以下标签：

*   `INDICATOR_NOISE`: 指标震荡导致的假信号（如金叉死叉频繁切换）。
*   `PATTERN_HALLUCINATION`: 识别出了不存在的形态（幻觉）。
*   `TREND_MISJUDGMENT`: 逆势交易（在强趋势中试图摸顶/抄底）。
*   `CONSERVATIVE_MISS`: 过于保守导致踏空。

### 3.2 优化建议生成 (Optimizer)
根据归因统计，生成具体建议：

*   **场景**: 如果发现 60% 的错误是因为“逆势摸顶”。
*   **建议**: "建议在 Decision Agent 的 Prompt 中增加规则：*当趋势报告显示 Strong Bullish 时，禁止仅凭 RSI 超买信号做空*。"

*   **场景**: 如果发现 Pattern Agent 经常识别错“头肩顶”。
*   **建议**: "建议降低 Pattern Agent 在综合决策中的权重，或切换 Vision 模型版本。"

---

## 4. 开发路线图 (Roadmap)

### 第一阶段：MVP (最小可行性产品)
- [ ] 实现 `case_filter.py`：支持从 CSV 中按“亏损幅度”和“信心分”筛选 Top 10 失败案例。
- [ ] 实现 `llm_judge.py`：构建核心 Prompt，让 LLM 对单个 JSON 进行复盘。
- [ ] 输出简单的 Markdown 报告，列出“错误原因总结”。

### 第二阶段：批量化与统计
- [ ] 支持批量分析数百个历史文件。
- [ ] 统计错误类型的分布（饼图）。
- [ ] 自动关联修改建议：将错误类型映射到具体的 Prompt 优化策略。

### 第三阶段：闭环验证
- [ ] 提供“一键回测”功能：修改 Prompt 后，自动重新跑这 10 个失败案例，看是否修正了决策。

---

## 5. 预期效果示例

**分析报告片段：**

> **🔴 典型失败案例 #1 (BTC-4H)**
> *   **决策**: SHORT (信心: High)
> *   **实际**: 价格上涨 5%
> *   **AI 诊断**:
>     *   Agent 过度依赖 **Stochastic 死叉** 信号。
>     *   忽视了 Trend Agent 报告中的 **"价格位于长期上升通道下轨"** 这一关键支撑信息。
>     *   **结论**: 权重分配错误，微观指标压倒了宏观趋势。
>
> **💡 优化建议**:
> *   修改 `decision_agent.py` 的 System Prompt，添加：
>     *   `"CRITICAL RULE: Never open a SHORT position solely based on oscillators if the Trend Report indicates price is at Major Support."`

---

## 6. 讨论事项

1.  **Token 消耗**: 批量分析需要消耗大量 Token，建议 MVP 阶段限制每次分析的案例数量（如每次只分析 5-10 个典型）。
2.  **模型选择**: 建议使用推理能力最强的模型（如 DeepSeek-R1 或 Claude 3.5 Sonnet）作为“教练”，即使 Agent 本身使用的是成本较低的模型。
