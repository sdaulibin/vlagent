---
description: 启动 vl_flow 开发环境（前后端服务）
---

# 启动开发环境

本工作流用于一键启动 vl_flow 项目的完整开发环境。

## 前置检查

1. 确认 Python 3.11+ 已安装
2. 确认 Node.js 18+ 已安装
3. 确认 Poppler 已安装（macOS: `brew install poppler`）

## 启动后端服务

// turbo
1. 进入后端目录并启动 FastAPI 服务：
```bash
cd /Users/binginx/PycharmProjects/vl_flow/backend && uv run uvicorn main:app --reload --port 8000
```

后端服务将运行在: http://localhost:8000
API 文档地址: http://localhost:8000/docs

## 启动前端服务

// turbo
2. 进入前端目录并启动 Vite 开发服务器：
```bash
cd /Users/binginx/PycharmProjects/vl_flow/frontend && npm run dev
```

前端服务将运行在: http://localhost:5173

## 验证服务

3. 验证两个服务都已正常启动：
   - 访问 http://localhost:5173 确认前端页面加载正常
   - 访问 http://localhost:8000/docs 确认后端 API 文档可访问

## 停止服务

如需停止服务，在对应终端按 `Ctrl+C` 即可。
