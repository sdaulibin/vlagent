# Frontend - VL_Flow

VL_Flow 前端应用，基于 Vue 3 + TypeScript + Tailwind CSS 构建。

## 功能特性

- **文件上传**: 支持拖拽上传银行流水 PDF
- **文件列表**: 查看已上传的文件及处理状态
- **交易展示**: 以表格形式展示识别出的交易记录
- **分页显示**: 支持分页浏览大量交易数据

## 技术栈

- **框架**: Vue 3 (Composition API)
- **语言**: TypeScript
- **样式**: Tailwind CSS
- **构建工具**: Vite
- **HTTP 客户端**: Axios

## 目录结构

```
frontend/
├── src/
│   ├── api/                # API 接口
│   │   └── index.ts
│   ├── assets/             # 静态资源
│   │   └── main.css
│   ├── components/         # 组件
│   │   ├── FileList.vue    # 文件列表
│   │   ├── FileUpload.vue  # 文件上传
│   │   └── ResultList.vue  # 结果展示
│   ├── types.ts            # 类型定义
│   ├── App.vue             # 主组件
│   └── main.ts             # 入口文件
├── index.html
├── package.json
├── tailwind.config.js
├── tsconfig.json
└── vite.config.ts
```

## 快速开始

### 1. 安装依赖

```bash
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

应用将在 http://localhost:5173 启动。

### 3. 构建生产版本

```bash
npm run build
```

## API 调用

前端通过 Axios 调用后端 API：

| 函数 | 接口 | 说明 |
|------|------|------|
| `uploadFile(file)` | `POST /api/files/upload` | 上传文件 |
| `getFiles()` | `GET /api/files` | 获取文件列表 |
| `getFileTransactions(id)` | `GET /api/transactions/{id}` | 获取交易记录 |

## 配置

API 基础地址配置在 `src/api/index.ts`：

```typescript
const api = axios.create({
    baseURL: 'http://localhost:8000/api',
});
```
