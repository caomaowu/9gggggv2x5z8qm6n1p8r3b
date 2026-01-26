# Meta-Analyzer (元分析系统)

Meta-Analyzer 是一个基于 AI 的交易复盘诊断工具。它扮演“交易审计员”的角色，通过对比 AI 交易 Agent 的历史决策与随后的实际市场走势，自动分析交易的成败原因，并提供优化建议。

## 🎯 核心功能

1.  **历史回测可视化**:
    - 自动扫描 `backend/data/history/` 目录下的所有交易记录。
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

### 2. 配置 LLM

Meta-Analyzer 使用独立的配置文件 `tools/meta_analyzer/.env`，以免影响主程序。

请在 `tools/meta_analyzer/` 目录下创建或修改 `.env` 文件：

```ini
# LLM Provider (支持 iflow, deepseek, openai, openrouter)
AGENT_PROVIDER=iflow
AGENT_MODEL=qwen3-max
AGENT_TEMPERATURE=0.2

# API Keys (根据选择的 Provider 填写)
IFLOW_API_KEY=sk-xxxxxxxx
DEEPSEEK_API_KEY=sk-xxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxx
```

### 3. 启动应用

在项目根目录下运行：

```bash
streamlit run tools/meta_analyzer/app.py
```

访问浏览器地址: `http://localhost:8501`

## 📂 目录结构

```text
tools/meta_analyzer/
├── app.py              # Streamlit 主程序入口
├── diagnosis.py        # 诊断 Agent 核心逻辑 (LLM 交互)
├── loader.py           # 数据加载与 PnL 计算模块
├── .env                # 独立配置文件
└── templates/
    └── critic_prompt.md # 诊断专用 Prompt 模板
```

## 🛠️ 常见问题

**Q: 为什么显示 "No Future Kline Data Available"?**
A: 这表示该历史记录 JSON 文件中缺少 `future_kline_data` 字段。这通常是因为在运行批量回测时未开启 `future_kline_count` 参数，或者是实盘实时分析的记录（尚未产生未来数据）。

**Q: 如何切换诊断模型？**
A: 修改 `tools/meta_analyzer/.env` 中的 `AGENT_PROVIDER` 和 `AGENT_MODEL` 即可。目前内置支持 `iflow`, `deepseek`, `openrouter` 等主流兼容 OpenAI 协议的接口。

**Q: 诊断报错 "LLM Client not initialized"?**
A: 请检查 `.env` 文件是否存在且 API Key 是否正确。系统启动时会在控制台打印 "Loaded environment variables..." 日志。
