# 🎨 Frontend Application

基于 **Vue 3.5** + **TypeScript** + **Tailwind CSS 4** 构建的现代化 Web 应用。提供银行流水识别、询证函识别与格式比对、证件识别、发票识别、合同比对等多种文档智能处理的可视化界面。

---

## 🚀 快速启动

### 📋 前置要求

- **Node.js 18+**
- **npm**

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
├── views/                           # 页面级组件 (7个功能页面)
│   ├── Home.vue                     # 首页导航
│   ├── BankStatement.vue            # 🏦 银行流水识别
│   ├── ConfirmationLetter.vue       # 📝 询证函识别
│   ├── FormatCompare.vue            # 📐 询证函格式比对
│   ├── CredentialRecognition.vue    # 🪪 证件识别
│   ├── InvoiceRecognition.vue       # 🧾 发票识别
│   └── ContractCompare.vue          # 📄 合同比对
├── components/                      # UI 组件
│   ├── bank-results/                # 银行汇总专用组件库 (11家银行按需加载)
│   ├── FileUpload.vue              # 通用文件上传组件
│   ├── FileList.vue                # 文件列表组件
│   ├── ResultList.vue              # 识别结果展示
│   ├── ContractUpload.vue          # 合同上传组件
│   ├── ContractResultView.vue      # 合同比对结果展示
│   ├── ContractHistory.vue         # 合同比对历史记录
│   ├── TiptapViewer.vue            # 富文本查看器
│   └── PowerOfAttorneyResult.vue   # 授权委托书结果展示
├── api/                            # 基于 Axios 的 API 请求封装
│   ├── index.ts                    #   通用文件/银行流水 API
│   ├── contract.ts                 #   合同比对 API
│   ├── confirmation.ts             #   询证函 API
│   ├── formatCompare.ts            #   格式比对 API
│   ├── invoice.ts                  #   发票识别 API
│   └── credential.ts               #   证件识别 API
├── router/                         # Vue Router 路由配置
├── assets/                         # 样式 (Tailwind 4) 与静态资源
└── types.ts                        # 全局 TypeScript 类型定义
```

### 🏦 动态 UI 渲染

系统根据后端返回的 `bank_type` 动态加载对应的汇总展示组件。

- **入口**: `src/components/bank-results/index.ts`
- **机制**: 使用 Vue 的 `<component :is="...">` 配合组件映射表实现。
- **已支持**: 工商银行、农业银行、中国银行、建设银行、交通银行、招商银行、光大银行、广发银行、邮储银行、济宁银行、齐鲁银行 (共 11 家)。

---

## 🆕 添加新银行 UI 支持

当后端新增支持一种银行时，前端需要完成以下步骤：

1. **创建组件**: 在 `src/components/bank-results/` 下创建 `XxxSummary.vue`。
2. **定义类型**: 在 `src/types.ts` 的 `BankType` 中添加新银行标识。
3. **注册组件**: 在 `src/components/bank-results/index.ts` 中导出并添加到 `bankSummaryComponents` 映射表中。

---

## 📋 核心功能实现

### 🏦 银行流水展示

- **ResultList.vue**: 核心容器，处理分页、Excel 导出逻辑以及多银行汇总的 Tab 切换。
- **自动适配**: 根据银行明细字段自动渲染表格列。

### 📝 询证函识别

- **ConfirmationLetter.vue**: 询证函管理页面，支持上传、AI 识别、结果编辑。
- **分离式数据**: 文件信息与识别结果从后端嵌套返回（`recognition` 对象），前端自动解析。
- **12 字段表单**: 函证编号、事务所名称、回函地址、联系人、电话、邮编、扣费账号、截止日期、起始日期、终止日期、印章日期、印章名称。

### 📐 询证函格式比对

- **FormatCompare.vue**: 格式比对页面，左侧模板预览 + 右侧上传文件对比。
- **差异展示**: 结构化内容对比，按严重级别高亮差异项。
- **模板选择**: 支持 3 种标准模板（格式一、格式二、验资报告）。

### 🪪 证件识别

- **CredentialRecognition.vue**: 多类型证件识别页面。
- **类型选择**: 支持身份证、电子印章、银行卡、授权委托书等 8 种类型。
- **结构化展示**: 根据证件类型动态渲染对应的结果字段。

### 🧾 发票识别

- **InvoiceRecognition.vue**: 发票上传与识别结果展示。
- **批量处理**: 支持多页发票，逐页展示识别结果。
- **状态轮询**: 后台异步识别，前端自动轮询处理状态。

### 📄 合同比对

- **ContractCompare.vue**: 合同上传与差异展示页面。
- **富文本展示**: 基于 Tiptap 3 的差异可视化渲染。

---

## 📦 技术栈详情

- **Framework**: Vue 3.5 (Composition API)
- **Language**: TypeScript 5.9
- **Styling**: Tailwind CSS 4.1
- **Editor**: Tiptap 3 (Headless rich-text editor)
- **HTTP Client**: Axios
- **Icons**: Lucide Vue Next
- **Build Tool**: Vite 7
