# Frontend - VL_Flow

基于 Vue 3 + TypeScript + Tailwind CSS 构建的智能文档识别前端。

## ✨ 功能特性

- 📂 **场景入口首页** - 多场景识别入口
- 📤 **文件上传** - 拖拽上传 PDF 文件
- 📋 **汇总展示** - 账户信息和收支统计
- 📊 **明细列表** - 分页展示交易记录

## 🛠️ 技术栈

- Vue 3 (Composition API)
- TypeScript
- Tailwind CSS
- Vue Router
- Axios

## 📁 目录结构

```
src/
├── views/                  # 页面
│   ├── Home.vue            # 首页入口
│   └── BankStatement.vue   # 银行流水识别
├── components/             # 组件
│   ├── FileUpload.vue      # 文件上传
│   ├── FileList.vue        # 文件列表
│   └── ResultList.vue      # 结果展示
├── router/                 # 路由
├── api/                    # API 接口
└── types.ts                # 类型定义
```

## 🚀 快速开始

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

访问 http://localhost:5173

## 🔗 路由

| 路径 | 页面 |
|------|------|
| `/` | 首页 - 场景选择 |
| `/bank-statement` | 银行流水识别 |

## 📡 API

| 函数 | 接口 |
|------|------|
| `uploadFile(file)` | `POST /api/files/upload` |
| `getFiles()` | `GET /api/files` |
| `getFileTransactions(id)` | `GET /api/transactions/{id}` |
| `getFileSummary(id)` | `GET /api/transactions/{id}/summary` |
