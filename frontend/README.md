# Frontend

Vue 3 + TypeScript + Tailwind CSS 构建的前端应用。

## 🚀 启动

```bash
npm install
npm run dev
```

访问 http://localhost:5173

## 📁 结构

```
src/
├── views/              # 页面
│   ├── Home.vue        # 首页入口
│   ├── BankStatement.vue # 银行流水识别页
│   └── ContractCompare.vue # 合同比对页
├── components/         # 组件
│   ├── FileUpload.vue
│   ├── FileList.vue
│   ├── ResultList.vue
│   ├── ContractResultView.vue # 比对结果查看器
│   └── TiptapViewer.vue       # 基于 Tiptap 的文档查看器
├── router/             # 路由
├── api/                # API 接口
├── assets/             # 样式
│   ├── main.css        # 通用样式
│   └── contract.css    # 合同页面样式
└── types.ts            # 类型定义
```

## 🔗 路由

| 路径 | 页面 |
|------|------|
| `/` | 首页 |
| `/bank-statement` | 银行流水识别 |
| `/contract-compare` | 合同智能比对 |

## 🧩 核心组件

### TiptapViewer
基于 Tiptap 编辑器的只读文档查看器，支持：
- HTML 内容渲染（表格、列表、标题）
- **智能高亮**：支持关键词、正则模糊匹配（忽略空格）
- 表格内容精准定位

### ContractResultView
合同比对结果展示组件，功能：
- 左右分栏显示原文档和比对文档
- 支持 PDF/图片/Word 格式预览
- 差异列表联动高亮

## 📡 API 函数

- `uploadFile(file)` - 上传文件
- `compareContracts(fileA, fileB)` - 发起合同比对任务
- `getTaskDiffs(taskId)` - 获取差异结果
- `getFilePreviewUrl(taskId, type)` - 获取文件预览链接
