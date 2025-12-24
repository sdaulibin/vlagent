# Frontend Application

基于 **Vue 3** + **TypeScript** + **Tailwind CSS** 构建的现代化前端应用。

## 🚀 开发指南

### 1. 安装依赖

```bash
npm install
```

### 2. 常用命令

| 命令 | 说明 |
| :--- | :--- |
| `npm run dev` | 启动开发服务器 (端口 5173) |
| `npm run build` | 构建生产环境代码 |
| `npm run preview` | 预览生产构建 |

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
│   ├── ResultList.vue      # 🆕 多银行识别结果展示
│   ├── ContractResultView.vue # 合同比对结果
│   └── TiptapViewer.vue    # 富文本查看器
├── api/                    # API 请求封装
├── router/                 # 路由配置
├── types.ts                # TypeScript 类型定义
└── assets/                 # 静态资源与样式
```

## 🏦 多银行支持

### 银行类型显示

`ResultList.vue` 组件支持动态展示不同银行的识别结果：

| 银行类型 | 汇总信息 | 明细字段 |
| :--- | :--- | :--- |
| **山东地方银行** | 收入/支出总笔数、总金额 | 交易时间、对方户名、摘要备注 |
| **光大银行** | 借方/贷方发生额、笔数 | 交易日期、借/贷、对方名称、流水号 |
| **招商银行** | 入账/出账总笔数、总金额 | 交易流水号、收付方名称、公司一卡通号 |
| **济宁银行** | 收入/支出笔数金额 | 交易时间、收付金额、对方信息 |
| **广发银行** | 收支笔数金额、账户余额 | 流水号、交易时间、对方账户、摘要附言 |

### 类型定义

```typescript
// types.ts
type BankType = 'shandong_local' | 'everbright' | 'cmb' | 'jining' | 'cgb';

interface Summary {
    bank_type: BankType;
    account_name?: string;
    // ... 各银行特有字段
}

interface Transaction {
    bank_type: BankType;
    // ... 各银行特有字段
}
```

## 🔗 路由说明

| 路径 | 组件 | 说明 |
| :--- | :--- | :--- |
| `/` | `Home.vue` | 应用首页 |
| `/bank-statement` | `BankStatement.vue` | 银行流水识别 |
| `/contract-compare` | `ContractCompare.vue` | 合同智能比对 |

## 🧩 核心组件

### `ResultList.vue`

银行流水识别结果展示组件，支持：
*   **银行类型标签**: 自动识别并显示银行类型
*   **动态汇总信息**: 根据银行类型显示对应字段
*   **多汇总Tab页**: 🆕 广发银行支持多个汇总切换显示
*   **条件明细列表**: 展示银行特有的交易字段
*   **分页浏览**: 支持大量交易记录分页

### `TiptapViewer` & `ContractResultView`

合同比对相关组件，支持双栏对比、差异高亮和同步滚动。
