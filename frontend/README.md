# 🎨 Frontend Application

基于 **Vue 3.5** + **TypeScript** + **Tailwind CSS 4** 构建的现代化 Web 应用。它提供了直观的界面，用于展示 AI 识别的银行流水结果以及合同智能比对的差异。

---

## 🚀 快速启动

### 📋 前置要求
- **Node.js 18+**
- **npm** 或 **pnpm**

### 🛠️ 安装与开发
1. **安装依赖**:
   ```bash
   npm install
   ```
2. **启动开发服务器**:
   ```bash
   npm run dev
   ```
   访问: [http://localhost:5173](http://localhost:5173)

3. **构建生产环境**:
   ```bash
   npm run build
   ```

---

## 🏗️ 项目架构

### 📁 目录结构
```bash
src/
├── views/           # 页面级组件 (Home, BankStatement, ContractCompare)
├── components/      # 基础 UI 组件
│   └── bank-results/# 🆕 银行汇总专用组件库 (按银行拆分)
├── api/             # 基于 Axios 的 API 请求封装
├── router/          # Vue Router 路由配置
├── assets/          # 样式 (Tailwind 4) 与静态资源
└── types.ts         # 全局 TypeScript 类型定义
```

### 🏦 动态 UI 渲染
系统会根据后端返回的 `bank_type` 动态加载对应的汇总展示组件。
- **入口**: `src/components/bank-results/index.ts`
- **机制**: 使用 Vue 的 `<component :is="...">` 配合组件映射表实现。

---

## 🆕 添加新银行 UI 支持
当后端新增支持一种银行时，前端需要完成以下步骤：

1. **创建组件**: 在 `src/components/bank-results/` 下创建 `XxxSummary.vue`。
2. **定义类型**: 在 `src/types.ts` 的 `BankType` 中添加新银行标识。
3. **注册组件**: 在 `src/components/bank-results/index.ts` 中导出并添加到 `bankSummaryComponents` 映射表中。

---

## 📋 核心功能实现

### 📑 银行流水展示
- **ResultList.vue**: 核心容器，处理分页、Excel 导出逻辑以及多银行汇总的 Tab 切换。
- **自动适配**: 根据银行明细字段自动渲染表格列。

### 📄 合同比对展示
- **TiptapViewer.vue**: 基于 Tiptap 3 的富文本展示，支持同步滚动。
- **差异高亮**: 通过 CSS 类名（`diff-added`, `diff-removed`, `diff-changed`）实时渲染差异内容。

---

## 📦 技术栈详情
- **Framework**: Vue 3.5 (Composition API)
- **Language**: TypeScript 5.9
- **Styling**: Tailwind CSS 4 (Next-gen CSS utility engine)
- **Editor**: Tiptap 3 (Headless rich-text editor)
- **Icons**: Lucide Vue Next
- **Build Tool**: Vite 6
