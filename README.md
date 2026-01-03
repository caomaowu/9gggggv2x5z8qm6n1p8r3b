# QuantAgent V2 - 重构版 (Refactored)

QuantAgent 是一个基于多智能体（Multi-Agent）的量化交易分析系统，结合了技术指标、形态识别和趋势分析，为用户提供全面的市场洞察。

本项目是 V2 重构版本，采用了前后端分离的现代化架构。

## 🏗 架构概览 (Architecture)

- **后端 (Backend)**: Python + FastAPI
  - 异步处理，高性能 API
  - 模块化服务架构 (Service Layer)
  - Pydantic 类型安全
  - WebSocket 实时进度推送
- **前端 (Frontend)**: React + TypeScript + Vite
  - 组件化 UI 开发
  - Zustand 全局状态管理
  - Tailwind CSS 现代化样式
  - 完整复刻原版经典布局

## 📂 目录结构 (Directory Structure)

```
refactor_v2/
├── backend/                # 后端代码
│   ├── app/
│   │   ├── api/            # API 路由定义
│   │   ├── core/           # 核心配置与事件
│   │   ├── services/       # 业务逻辑 (交易引擎、行情服务、HTML导出)
│   │   ├── models/         # 数据模型
│   │   ├── agents/         # AI 智能体 (LangGraph)
│   │   ├── utils/          # 通用工具
│   └── .env.example        # 环境变量示例
│
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── api/            # API 请求封装
│   │   ├── components/     # UI 组件
│   │   ├── store/          # Zustand 状态管理
│   │   └── types/          # TypeScript 类型定义
│   ├── public/             # 静态资源
│   └── package.json        # 前端依赖
│
├── tools/                  # 辅助工具
│   └── auto_pdf.py         # HTML 转 PDF 自动化脚本
│
├── exports/                # 分析报告输出目录 (按日期自动归档)
│   ├── 2026-01-01/
│   ├── 2026-01-02/
│   └── ...
│
└── start_all.py            # 一键启动脚本 (Python版)
├── requirements.txt        # 项目整体依赖
```

## 🚀 快速开始 (Quick Start)

### 方式一：一键启动 (推荐)

在项目根目录下运行 Python 脚本，即可同时启动后端、前端和 PDF 转换工具：

```bash
python start_all.py
```
*该脚本会自动打开三个新的终端窗口运行各服务。*

### 方式二：手动分步启动

#### 1. 后端启动 (Backend)

确保您已安装 Python 3.10+。

```bash
# 1. 进入后端目录
cd backend

# 2. 创建并激活虚拟环境 (可选但推荐)
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. 安装依赖
pip install -r ../requirements.txt

# 4. 配置环境变量
# 复制示例文件为 .env，并填入您的 API Key
cp .env.example .env

# 5. 启动服务
uvicorn app.main:app --reload
```

后端服务将在 `http://localhost:8000` 启动。
API 文档地址: `http://localhost:8000/docs`

#### 2. 前端启动 (Frontend)

确保您已安装 Node.js 18+。

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev
```

前端页面将在 `http://localhost:5173` 启动。

#### 3. PDF 自动化工具 (可选)

该工具会自动监控 `exports` 目录，将新生成的 HTML 报告自动转换为 PDF。

**依赖安装:**
```bash
pip install playwright
playwright install chromium
```

**启动工具:**
```bash
python tools/auto_pdf.py
```

## ✨ 主要功能 (Features)

- **多模态分析**: 支持 OpenAI、DeepSeek、Qwen 等多种大模型进行市场分析。
- **多模型支持**: 内置多种决策模型版本（约束版/宽松版/综合版）。
- **灵活的数据源**:
  - 实时最新数据
  - 历史日期范围回测
  - 指定时间点复盘
- **资产管理**: 支持自定义添加交易对，具备管理模式。
- **实时进度**: 通过 WebSocket 实时展示分析步骤和状态。
- **自动报告**:
  - 自动生成独立的 HTML 报告（包含所有资源，可离线查看）
  - 自动按日期归档保存 (`exports/YYYY-MM-DD/`)
  - 支持自动转换为 PDF 格式
- **历史记录与恢复**:
  - 自动保存每次分析的完整 JSON 数据
  - 前端支持查看最近的历史分析记录
  - 刷新页面可自动恢复上次未关闭的分析结果

## 📝 开发指南

- **后端开发**: 主要逻辑位于 `app/services/trading_engine.py` (交易核心) 和 `app/api/v1/endpoints/analyze.py` (接口层)。
- **前端开发**: 主要页面组件位于 `src/components/AnalysisForm.tsx`，状态管理位于 `src/store/useAppStore.ts`。

## ⚠️ 注意事项

- 本项目依赖外部行情 API (如 caomao.xyz) 和 LLM API，请确保 `.env` 中的 Token 和 Key 配置正确。
- 首次运行时，前端需要下载依赖，请保持网络通畅。
