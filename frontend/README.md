# Frontend Application

基于 **Vue 3.5** + **TypeScript 5.9** + **Tailwind CSS 4** 构建的现代化前端应用。

## 🚀 开发指南

### 1. 安装依赖

```bash
npm install
```

### 2. 常用命令

| 命令              | 说明                       |
| :---------------- | :------------------------- |
| `npm run dev`     | 启动开发服务器 (端口 5173) |
| `npm run build`   | 构建生产环境代码           |
| `npm run preview` | 预览生产构建               |

启动后访问: http://localhost:5173

## 📁 项目结构

```
src/
├── views/                  # 页面视图
│   ├── Home.vue            # 首页
│   ├── BankStatement.vue   # 银行流水识别页
│   └── ContractCompare.vue # 合同比对页
├── components/             # 组件
│   ├── FileUpload.vue      # 文件上传
│   ├── FileList.vue        # 文件列表
│   ├── ResultList.vue      # 识别结果展示 (容器组件)
│   ├── bank-results/       # 🆕 银行汇总组件 (按银行拆分)
│   │   ├── index.ts            # 组件索引与动态映射
│   │   ├── ShandongSummary.vue
│   │   ├── EverbrightSummary.vue
│   │   ├── CmbSummary.vue
│   │   ├── JiningSummary.vue
│   │   ├── CgbSummary.vue
│   │   ├── PsbcSummary.vue
│   │   ├── IcbcSummary.vue
│   │   └── CcbSummary.vue
│   ├── ContractUpload.vue  # 合同上传
│   ├── ContractHistory.vue # 合同历史记录
│   ├── ContractResultView.vue # 合同比对结果
│   └── TiptapViewer.vue    # 富文本查看器
├── api/                    # API 请求封装
├── router/                 # 路由配置
├── types.ts                # TypeScript 类型定义
└── assets/                 # 静态资源与样式
```

## 🏦 多银行支持

### 支持的银行类型

| 银行类型         | 汇总信息                   | 明细字段                                     |
| :--------------- | :------------------------- | :------------------------------------------- |
| **山东地方银行** | 收入/支出总笔数、总金额    | 交易时间、对方户名、摘要备注                 |
| **光大银行**     | 借方/贷方发生额、笔数      | 交易日期、借/贷、对方名称、流水号            |
| **招商银行**     | 入账/出账总笔数、总金额    | 交易流水号、收付方名称、公司一卡通号         |
| **济宁银行**     | 收入/支出笔数金额          | 交易时间、收付金额、对方信息                 |
| **广发银行**     | 收支笔数金额、账户余额     | 流水号、交易时间、对方账户、摘要附言         |
| **邮储银行**     | 收支总金额、总笔数         | 交易时间、对方行名、用途、附言               |
| **工商银行**     | 本方账号户名、币种、开户行 | 交易时间、转入/转出金额、对方单位、用途      |
| **建设银行**     | 本方户名、打印日期         | 交易时间、借贷金额、对方开户机构、交易流水号 |

### 类型定义

```typescript
// types.ts
type BankType =
  | "shandong_local"
  | "everbright"
  | "cmb"
  | "jining"
  | "cgb"
  | "psbc"
  | "icbc"
  | "ccb";

interface Summary {
  bank_type: BankType;
  account_name?: string;
  account_number?: string;
  // ... 各银行特有字段
}

interface Transaction {
  bank_type: BankType;
  id: number;
  // ... 各银行特有字段
}
```

## 🔗 路由说明

| 路径                | 组件                  | 说明         |
| :------------------ | :-------------------- | :----------- |
| `/`                 | `Home.vue`            | 应用首页     |
| `/bank-statement`   | `BankStatement.vue`   | 银行流水识别 |
| `/contract-compare` | `ContractCompare.vue` | 合同智能比对 |

## 📦 主要依赖

| 包名              | 版本     | 用途         |
| :---------------- | :------- | :----------- |
| `vue`             | ^3.5.24  | 前端框架     |
| `vue-router`      | ^4.6.4   | 路由管理     |
| `axios`           | ^1.13.2  | HTTP 客户端  |
| `tailwindcss`     | ^4.1.17  | 原子化 CSS   |
| `@tiptap/vue-3`   | ^3.13.0  | 富文本编辑器 |
| `lucide-vue-next` | ^0.556.0 | 图标库       |

### Tiptap 扩展

- `@tiptap/starter-kit` - 基础功能包
- `@tiptap/extension-highlight` - 高亮标记
- `@tiptap/extension-table` - 表格支持

## 🧩 核心组件

### `ResultList.vue`

银行流水识别结果展示容器组件，特性：

- **银行类型标签**: 自动识别并显示银行类型
- **动态汇总组件**: 🆕 根据银行类型动态加载对应汇总组件
- **多汇总 Tab 页**: 广发银行支持多个汇总切换显示
- **条件明细列表**: 展示银行特有的交易字段
- **分页浏览**: 支持大量交易记录分页
- **Excel 导出**: 一键导出识别结果

### `bank-results/` 组件目录

各银行汇总信息独立组件，通过 `<component :is>` 动态渲染：

- `ShandongSummary.vue` - 山东地方银行
- `EverbrightSummary.vue` - 光大银行
- `CmbSummary.vue` - 招商银行
- `JiningSummary.vue` - 济宁银行
- `CgbSummary.vue` - 广发银行
- `PsbcSummary.vue` - 邮储银行
- `IcbcSummary.vue` - 工商银行
- `CcbSummary.vue` - 建设银行

### `TiptapViewer.vue` & `ContractResultView.vue`

合同比对相关组件，特性：

- 双栏对比视图
- 差异高亮显示 (新增/删除/修改)
- 同步滚动
- 导出差异报告

## 🎨 样式说明

项目使用 Tailwind CSS 4 + PostCSS：

```
postcss.config.js       # PostCSS 配置
tailwind.config.js      # Tailwind 配置
src/style.css           # 全局样式
src/assets/             # 自定义样式资源
```
