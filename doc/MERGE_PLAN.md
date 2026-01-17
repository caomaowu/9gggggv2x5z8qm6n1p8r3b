# RefactorV2 与 NoFx 深度融合计划文档 (Rev 2.0)

本文档详细描述了如何将本地的高级分析引擎 (RefactorV2) 作为**深度分析插件**集成到开源交易操作系统 (NoFxAiOS/nofx) 中。

**核心理念：复用 NoFx 强大的交易执行能力，RefactorV2 仅作为“军师”提供分析建议。**

## 1. 核心目标

构建 **"NoFx (主系统) + Python 分析插件 (Sidecar)"** 架构。

- **NoFx (Host)**: 负责账户管理、行情接入、订单执行、风控管理（复用现有功能）。
- **RefactorV2 (Plugin)**: 负责多维度深度分析、图表生成、AI 决策推理。
- **集成模式**: 
    - 前端：RefactorV2 分析页面作为 NoFx 的一个功能模块嵌入。
    - 后端：分析结果转化为标准信号，手动或自动推送给 NoFx Trader 执行。

## 2. 架构设计

### 2.1 整体拓扑

```mermaid
graph TD
    User[用户] --> NoFxWeb[NoFx Web 控制台]
    
    subgraph "NoFx 系统边界"
        TraderPage[交易员页面]
        DeepAnalyzeBtn[✨ 深度分析按钮]
        
        TraderManager[Trader Manager (Go)]
        Execution[执行引擎 (Go)]
    end
    
    subgraph "Python 分析插件 (原 RefactorV2)"
        PyAPI[FastAPI 分析服务]
        DeepThink[深度思考引擎]
    end
    
    DeepAnalyzeBtn -- "1. 调用分析 API" --> PyAPI
    PyAPI -- "2. 返回 JSON 报告 & 建议参数" --> NoFxWeb
    
    User -- "3. 确认采用策略" --> NoFxWeb
    NoFxWeb -- "4. 下达交易指令 (Symbol, Side, TP/SL)" --> TraderManager
    TraderManager --> Execution
```

### 2.2 数据流转

1.  **触发分析**: 用户在 NoFx 界面选中某个 Trader 或币种，点击“深度分析”。
2.  **获取建议**: 前端请求 Python 服务，Python 服务独立拉取行情（或由 NoFx 传入），进行多模型分析。
3.  **展示结果**: 弹窗展示分析详情（K线图、AI 观点、置信度）。
4.  **执行决策**: 
    - 界面提供 **"一键执行"** 按钮，预填充 Python 建议的参数（方向、杠杆、止盈止损）。
    - 用户点击确认后，调用 NoFx 原生交易接口 `/api/traders/{id}/orders` (或类似接口) 完成下单。

## 3. 执行步骤 (Step-by-Step)

### 阶段一：环境与代码库准备

- [ ] **仓库整合**:
    - 克隆 `NoFxAiOS/nofx`。
    - 将 `refactor_v2/backend` 移入 `nofx/plugins/analytics-engine`（重命名以明确意图）。
    - 保持 Python 服务独立运行，不侵入 Go 核心代码。
- [ ] **服务编排**:
    - 更新 `docker-compose.yml`，增加 `analytics-service` 容器。
    - 配置内部网络，允许 NoFx 前端通过反向代理访问 Python 服务。

### 阶段二：前端集成 (Frontend Integration)

- [ ] **组件移植**:
    - 将 `refactor_v2` 的核心分析组件 (`AnalysisResult`, `FutureKlinePanel`) 移植到 `nofx/web/src/components/Analytics`。
    - 适配 NoFx 的 UI 风格 (Tailwind CSS, Dark Mode)。
- [ ] **功能入口**:
    - 在 `TraderDetails` 页面增加 **"AI 深度分析"** 按钮。
    - 点击按钮弹出模态框 (Modal)，加载分析组件。
- [ ] **API 联调**:
    - 在 `nofx/web/vite.config.ts` 中添加代理规则，转发 `/api/analytics` 请求到 Python 服务。

### 阶段三：交易链路打通 (Signal to Action)

- [ ] **信号转化**:
    - 在前端实现逻辑：将 Python 返回的 `decision` 对象（包含 `action`, `stop_loss`, `take_profit`）映射为 NoFx 的下单表单数据。
- [ ] **执行对接**:
    - 复用 NoFx 现有的 `Manual Trade` 或 `Strategy Execution` 接口。
    - 确保下单请求包含完整的风控参数。

## 4. 技术栈清单

| 模块 | 技术栈 | 说明 |
| :--- | :--- | :--- |
| **主系统** | Go, Gin, GORM | NoFx 原生，负责一切交易行为 |
| **分析插件** | Python, FastAPI, LangChain | 只负责计算和生成建议，不持有私钥 |
| **前端** | React, TypeScript, Tailwind | 统一在 NoFx 项目中开发 |
| **数据源** | CCXT (Python) / NoFx DataFeed | 初期 Python 独立获取，后期可复用 Go 端数据 |

## 5. 优势

1.  **安全性高**: Python 端不接触用户 API Key 和私钥，只输出公开的分析结果。
2.  **稳定性强**: 交易执行逻辑完全依赖经过验证的 NoFx 核心，避免重复造轮子。
3.  **开发快**: 只需打通“前端展示”和“参数传递”两个环节即可。
