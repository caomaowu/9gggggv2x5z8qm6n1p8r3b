# Meta-Analyzer (元分析系统)

Meta-Analyzer 是一个基于 AI 的交易复盘诊断工具。它扮演“交易审计员”的角色，通过对比 AI 交易 Agent 的历史决策与随后的实际市场走势，自动分析交易的成败原因，并提供优化建议。

## 🎯 核心功能

1.  **历史回测可视化**:
    - 自动扫描历史交易记录。
    - 智能计算每笔交易的实际最大盈亏 (Max Profit / Max Drawdown)。
    - 使用 Plotly 交互式图表展示交易发生后的未来 K 线走势。

2.  **多维数据筛选**:
    - **时间**: 按日期过滤案例。
    - **资产**: 筛选特定交易对 (如 BTC/USDT)。
    - **结果**: 快速定位 "Win" (大赚), "Loss" (大亏), 或 "Choppy" (震荡) 的案例。
    - **方向**: 筛选做多 (LONG) 或做空 (SHORT) 决策。

3.  **AI 智能诊断**:
    - **归因分析**: 自动判断交易失败是由于信号噪音、形态失效、趋势误判还是外部事件。
    - **逻辑评分**: 对 Agent 当时的决策逻辑进行打分 (0-100)。
    - **改进建议**: 提供具体的 Prompt 或参数优化建议。

## 🚀 快速开始

### 1. 环境准备

确保已安装项目依赖：

```bash
pip install streamlit plotly pandas python-dotenv langchain-openai
```

### 2. 配置 LLM (全新架构)

Meta-Analyzer 现在使用完全独立的配置系统，支持所有兼容 OpenAI 协议的 LLM 提供商 (如 DeepSeek, iFlow, OpenRouter, OpenAI 等)。

请在 `tools/meta_analyzer/` 目录下复制 `.env.example` 为 `.env` 并填入配置：

```bash
cp tools/meta_analyzer/.env.example tools/meta_analyzer/.env
```

`.env` 配置示例：

```ini
# 必填: 您的 API Key
LLM_API_KEY=sk-xxxxxxxxxxxxxxxx

# 必填: API Base URL (例如 DeepSeek)
LLM_BASE_URL=https://api.deepseek.com/v1

# 必填: 模型名称
LLM_MODEL=deepseek-chat

# 可选: 温度 (默认 0.2)
LLM_TEMPERATURE=0.2

# 可选: 自定义数据目录 (默认指向 ../../backend/data/history)
# DATA_DIR=/path/to/custom/history
```

### 3. 启动应用

在项目根目录下运行：

```bash
streamlit run tools/meta_analyzer/app.py
```

或者在 `tools/meta_analyzer` 目录下运行：

```bash
cd tools/meta_analyzer
streamlit run app.py
```

访问浏览器地址: `http://localhost:8501`

## 📂 目录结构

```text
tools/meta_analyzer/
├── app.py              # Streamlit 主程序入口
├── config.py           # 独立配置管理模块
├── diagnosis.py        # 诊断 Agent 核心逻辑
├── loader.py           # 数据加载与 PnL 计算模块
├── .env                # 配置文件 (需手动创建)
└── templates/
    └── critic_prompt.md # 诊断专用 Prompt 模板
```

## 🛠️ 常见问题

**Q: 为什么显示 "No Future Kline Data Available"?**
A: 这表示该历史记录 JSON 文件中缺少 `future_kline_data` 字段。这通常是因为在运行批量回测时未开启 `future_kline_count` 参数，或者是实盘实时分析的记录（尚未产生未来数据）。

**Q: 如何切换诊断模型？**
A: 修改 `tools/meta_analyzer/.env` 中的 `LLM_MODEL` 和 `LLM_BASE_URL` 即可即时生效 (需要重启 Streamlit)。

**Q: 诊断报错 "LLM Client not initialized"?**
A: 请检查 `tools/meta_analyzer/.env` 文件是否存在且 `LLM_API_KEY` 是否正确配置。
