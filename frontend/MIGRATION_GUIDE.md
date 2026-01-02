# QuantAgent 前端重构与架构升级指南 (Refactor V2)

## 1. 项目现状概览

当前项目处于从 **Flask SSR (服务端渲染)** 向 **React SPA (单页应用)** 迁移的过渡阶段。我们已经完成了核心页面的 React 组件化复刻，但尚未实现完全的架构现代化。

### 1.1 当前状态
*   **物理架构**: 前后端已分离。后端仅负责 API 数据计算，前端 (refactor_v2) 接管 UI 展示。
*   **组件化**: 主要功能模块已拆分为 React 组件 (`SummaryPanel`, `DecisionPanel` 等)。
*   **样式管理**: **混合模式**。使用了原子化 CSS (Tailwind) 的理念，但底层布局和基础样式仍严重依赖原版的 `demo_new.css`。
*   **数据流**: 使用 `Zustand` (`useAppStore`) 进行全局状态管理，替代了原有的 Jinja2 模板变量传递。

---

## 2. 架构升级路线图 (Migration Roadmap)

为了实现真正的现代化架构，建议按照以下阶段进行升级：

### 第一阶段：样式隔离与模块化 (CSS Modularization)
**目标**: 彻底移除对 `demo_new.css` 的全局依赖，消除样式冲突风险。

1.  **引入 CSS Modules**:
    *   将 `.css` 文件重命名为 `.module.css`。
    *   在组件中通过 `import styles from './Component.module.css'` 引用。
    *   替换 JSX 中的 `className="panel"` 为 `className={styles.panel}`。

2.  **Tailwind CSS 全面替代**:
    *   **布局**: 用 `flex`, `grid`, `w-1/2` 等 Utility Classes 替代 Bootstrap 风格的 `row`, `col-md-*`。
    *   **间距**: 用 `p-4`, `m-2`, `gap-4` 替代自定义的 padding/margin。
    *   **颜色**: 在 `tailwind.config.js` 中定义 `etrade-purple` 主题色，替换 CSS 变量。

3.  **移除遗留 CSS**:
    *   一旦所有组件都完成了样式迁移，从 `index.html` 中删除 `<link rel="stylesheet" href="/assets/css/demo_new.css">`。

### 第二阶段：组件深度解耦 (Component Decoupling)
**目标**: 让组件更加纯粹，只关注 Props 输入，减少对全局 Store 的直接依赖。

1.  **UI 与逻辑分离 (Container/Presentational Pattern)**:
    *   **UI 组件**: 只负责渲染，数据通过 Props 传入 (e.g., `<StatCard value={100} label="Data Points" />`)。
    *   **容器组件**: 负责从 Store 获取数据并传递给 UI 组件。

2.  **通用组件库建设**:
    *   提取基础组件：`Button`, `Card`, `Badge`, `LoadingSpinner`。
    *   统一交互风格：Hover 效果、点击反馈、动画过渡。

### 第三阶段：工程化与性能优化 (Engineering & Performance)
**目标**: 提升开发体验和用户加载速度。

1.  **代码分割 (Code Splitting)**:
    *   使用 `React.lazy` 和 `Suspense` 动态加载路由组件 (如 `AnalysisResult`)，减少首屏体积。

2.  **API 层标准化**:
    *   封装统一的 Axios 请求实例，处理拦截器、错误提示和 Loading 状态。
    *   使用 `React Query` (TanStack Query) 管理服务端数据状态，实现缓存和自动重试。

3.  **类型安全 (TypeScript Strict Mode)**:
    *   完善 API 响应数据的 Interface 定义 (`AnalysisResult` 类型目前较为宽松)。
    *   开启 `strict: true`，消除所有 `any` 类型。

---

## 3. 关键迁移任务清单 (Checklist for Next AI)

请后续开发者按照以下清单执行任务：

### 🚨 优先级高 (High Priority)
- [ ] **样式去全局化**: 挑选一个简单的组件 (如 `SummaryPanel`)，尝试将其样式完全转换为 Tailwind 或 CSS Modules，验证脱离 `demo_new.css` 后是否正常。
- [ ] **栅格系统替换**: 查找所有 `col-md-*` 类名，替换为 Tailwind 的 Grid 系统 (`grid-cols-1 md:grid-cols-3`)。
- [ ] **图标库优化**: 目前通过 CDN 引入 FontAwesome，建议改为按需引入的 React Icon 组件 (`react-icons`) 以减少网络请求。

### 🟡 优先级中 (Medium Priority)
- [ ] **路由完善**: 使用 `react-router-dom` 建立正式的路由配置，支持浏览器后退/前进按钮（目前是基于状态的条件渲染）。
- [ ] **错误边界**: 添加 `ErrorBoundary` 组件，防止某个面板报错导致整个页面崩溃。
- [ ] **Loading 骨架屏**: 为各个面板添加加载时的 Skeleton 占位图，提升等待体验。

### 🟢 优先级低 (Low Priority)
- [ ] **暗黑模式完善**: 目前通过 JS 判断系统主题，建议结合 Tailwind 的 `dark:` 修饰符实现完美切换。
- [ ] **国际化 (i18n)**: 抽离硬编码的中文文本，使用 `react-i18next` 支持多语言。

---

## 4. 常用命令与资源

*   **启动开发服务器**: `npm run dev` (在 `refactor_v2/frontend` 目录下)
*   **构建生产版本**: `npm run build`
*   **当前核心文件**:
    *   入口: `src/App.tsx`
    *   状态: `src/store/useAppStore.ts`
    *   遗留样式: `public/assets/css/demo_new.css`

---
*文档生成时间: 2026-01-02*
*适用版本: Refactor V2*
