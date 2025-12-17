# Frontend Application

基于 **Vue 3** + **TypeScript** + **Tailwind CSS** 构建的现代化前端应用，提供直观的文档比对与分析界面。

## 🚀 开发指南

### 1. 安装依赖

```bash
npm install
```

### 2. 配置环境变量

在前端根目录创建 `.env` 文件 (如有需要)，配置 API 地址：

```ini
VITE_API_BASE_URL=http://localhost:8000
```

### 3. 常用命令

| 命令 | 说明 |
| :--- | :--- |
| `npm run dev` | 启动开发服务器 (默认端口 5173) |
| `npm run build` | 构建生产环境代码 |
| `npm run preview` | 预览生产构建结果 |
| `npm run lint` | 运行代码检查 |

启动后访问: http://localhost:5173

## 📁 项目结构

```
src/
├── views/              # 页面视图
│   ├── Home.vue          # 首页入口
│   ├── BankStatement.vue # 银行流水识别页
│   └── ContractCompare.vue # 合同智能比对页
├── components/         # 公共组件
│   ├── FileUpload.vue    # 文件上传组件
│   ├── FileList.vue      # 文件列表展示
│   ├── ContractResultView.vue # (核心) 左右分栏比对结果查看器
│   └── TiptapViewer.vue       # (核心) 基于 Tiptap 的富文本查看器
├── api/                # API 请求封装 (Axios)
├── router/             # Vue Router 路由配置
├── assets/             # 静态资源
│   ├── main.css          # 全局样式
│   └── contract.css      # 合同页面专用样式
└── types.ts            # TypeScript 类型定义
```

## 🔗 路由说明

| 路径 | 组件 | 说明 |
| :--- | :--- | :--- |
| `/` | `Home.vue` | 应用首页 |
| `/bank-statement` | `BankStatement.vue` | 银行流水识别及结果展示 |
| `/contract-compare` | `ContractCompare.vue` | 文档上传与智能比对 |

## 🧩 核心组件详解

### `TiptapViewer`
基于 [Tiptap](https://tiptap.dev/) 的高度定制化只读编辑器，主要功能包括：
*   **HTML 渲染**: 完美还原文档中的表格、列表、标题等格式。
*   **智能高亮**: 支持基于关键词或正则的动态高亮，自动忽略多余的空白字符。
*   **精准定位**: 可通过 API 滚动到文档的特定位置 (如差异点)。

### `ContractResultView`
专为合同比对设计的可视化组件：
*   **双栏布局**: 左侧显示原文档，右侧显示比对文档，支持同步滚动。
*   **多格式预览**: 集成 PDF、图片及 Word (HTML转换) 的预览能力。
*   **差异联动**: 点击差异列表中的项，自动在文档视图中高亮并定位到对应位置。

## 📡 关键 API 函数

位于 `src/api` 目录：

*   `uploadFile(file)`: 上传文件至后端。
*   `compareContracts(fileA, fileB)`: 提交两个文件 ID 进行比对。
*   `getTaskDiffs(taskId)`: 获取比对任务生成的详细差异数据。
*   `getFilePreviewUrl(taskId, type)`: 获取用于前端展示的文件预览链接。
