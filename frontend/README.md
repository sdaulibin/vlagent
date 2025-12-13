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
│   └── BankStatement.vue
├── components/         # 组件
│   ├── FileUpload.vue
│   ├── FileList.vue
│   └── ResultList.vue
├── router/             # 路由
├── api/                # API 接口
├── assets/main.css     # 全局样式
└── types.ts            # 类型定义
```

## 🔗 路由

| 路径 | 页面 |
|------|------|
| `/` | 首页 |
| `/bank-statement` | 银行流水识别 |

## 📡 API 函数

- `uploadFile(file)` - 上传文件
- `getFiles()` - 获取文件列表
- `deleteFile(id)` - 删除文件
- `getFileTransactions(id)` - 获取交易明细
- `getFileSummary(id)` - 获取汇总信息
