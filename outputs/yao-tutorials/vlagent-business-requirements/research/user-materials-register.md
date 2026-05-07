# User Materials Register

| id | type | title_or_label | user_priority | use_for | key_takeaway | limits_or_cautions |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | project doc | docs/项目简介.md | must_use | project overview, tech stack, architecture | VLAgent 是 AI 驱动的金融文档识别平台，7 大功能模块，前后端分离架构 | 用户自述文档，需与代码交叉验证 |
| U2 | project doc | docs/需求规格说明书.md | must_use | functional requirements, non-functional requirements, API specs, data models | 57 个 API 端点，34 张数据库表，涵盖 7 大功能模块的详细需求编号 | 基于已实现功能倒推，非前瞻性需求 |
| U3 | source code | vlagent-backend/ (full analysis) | must_use | backend architecture, bank handlers, services | FastAPI + SQLModel + Qwen-VL，11 家银行策略模式，异步任务处理 | 需注意配置文件中的敏感信息不暴露 |
| U4 | source code | vlagent-frontend/ (full analysis) | must_use | frontend architecture, views, components | Vue 3 + TypeScript + Vite 7，9 个页面组件，iframe 嵌入认证 | 无独立状态管理库 |
