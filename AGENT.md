# AGENT.md - VL Flow 项目配置

> 本文件为 AI 助手提供项目上下文和开发规范。

## 项目概述

基于 Qwen-VL 大模型的智能文档识别与分析平台，支持银行流水识别和合同比对。

## 技术栈

| 层     | 技术                                  |
| :----- | :------------------------------------ |
| 前端   | Vue 3.5 + TypeScript + Tailwind CSS 4 |
| 后端   | FastAPI + SQLModel + Python 3.11      |
| 包管理 | uv (后端) / npm (前端)                |
| AI     | Qwen-VL / 通义千问 VL                 |

## 目录结构

```
vl_flow/
├── frontend/                 # Vue 3 前端
│   └── src/components/
│       └── bank-results/     # 按银行拆分的汇总组件
├── backend/
│   ├── src/
│   │   ├── banks/            # 银行处理器 (策略模式)
│   │   ├── models/           # 按银行拆分的数据模型
│   │   └── transactions/     # 统一导出入口
│   ├── config/
│   │   ├── bank_schemas/     # 银行 Schema (JSON)
│   │   └── prompts/          # 按银行拆分的 AI 提示词
│   └── lib/                  # Java SDK (文件下载)
└── .agent/workflows/         # 工作流配置
```

## 开发规范

### 添加新银行模板

1. **后端**：创建 `src/banks/{bank}_handler.py`，继承 `BankHandler`，使用 `@register_bank` 装饰器
2. **模型**：创建 `src/models/{bank}_models.py`，在 `transactions/models.py` 中导出
3. **提示词**：创建 `config/prompts/{bank}.json`
4. **前端**：创建 `components/bank-results/{Bank}Summary.vue`，在 `index.ts` 中注册

### 常用命令

```bash
# 启动后端
cd backend && uv run uvicorn main:app --reload --port 8000

# 启动前端
cd frontend && npm run dev

# 运行 Java SDK 测试
cd backend && uv run python tests/test_download.py
```

### Git 提交规范

- `feat:` 新功能
- `fix:` 修复
- `refactor:` 重构
- `docs:` 文档

## 工作流

| 命令        | 说明                   |
| :---------- | :--------------------- |
| `/add-bank` | 添加新银行流水识别模板 |
| `/dev`      | 启动开发环境           |

## 注意事项

- `backend/lib/` 目录被 gitignore，包含 Java SDK 和敏感配置
- 银行模型使用 SQLModel，表名自动转小写
- 前端组件使用 `<component :is>` 动态渲染

## 常见错误 (避免踩坑)

### 1. 循环导入问题

**错误**：将银行模型放在 `src/banks/*_models.py` 会导致循环导入。

**原因**：`banks/__init__.py` 自动导入所有 handler → handler 导入 models → models 导入触发 `banks/__init__.py` 加载 → 循环。

**正确做法**：银行模型放在独立的 `src/models/` 目录，不要放在 `src/banks/` 目录下。

### 2. Handler 导入路径

**错误**：Handler 从 `src.transactions.models` 导入模型。

**正确做法**：Handler 直接从 `src.models.*_models` 导入对应模型，避免通过统一入口。

### 3. gitignore 文件访问

**错误**：使用 view_file 工具访问被 gitignore 的文件会失败。

**正确做法**：使用 `run_command` 的 `cat` 命令读取被 gitignore 的文件。

### 4. Python 虚拟环境

**错误**：使用 `.venv/bin/pip` 或 `.venv/bin/python`。

**正确做法**：本项目使用 uv 管理依赖，使用 `uv run python` 和 `uv add` 命令。
