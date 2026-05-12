# vlagent 上游数据同步设计文档

## 1. 背景与目标

### 1.1 背景

vlagent 当前使用本地 `modules` 和 `user_permissions` 表管理功能模块和用户权限。上游 IOA 系统已有完善的用户管理（`sys_user`）和智能体管理（`hi_agent_list`）体系，vlagent 的用户和权限应从上游统一管控。

### 1.2 目标

- 权限在上游 IOA 系统配置，vlagent 通过定时任务同步到本地
- vlagent 前后端 API 接口不变，前端无需任何改动
- 上游库短暂不可用时 vlagent 仍可正常运行（使用本地缓存数据）
- 上游系统改动最小（仅插入 7 条 `hi_agent_list` 子模块记录）

### 1.3 约束

- 上游数据库为只读，vlagent 不修改上游数据
- 上游系统代码不可修改

---

## 2. 数据模型

### 2.1 上游数据源（ioa 库）

数据库：`ioa` @ `10.238.146.99:30432`

#### `hi_agent_list`（智能体卡片表）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer | 主键 |
| name | varchar(255) | 名称 |
| url | varchar(255) | 访问地址 |
| description | varchar(255) | 描述 |
| pid | integer | 父级 ID（0=顶级） |
| sorting | integer | 排序 |
| is_delete | boolean | 软删除 |
| is_show | integer | 是否显示（0=隐藏, 1=显示） |
| permissions | boolean | 权限控制开关 |

vlagent 主入口 id=46（"智能文档识别智能体"），需要新增 7 条子模块记录（pid=46）。

#### `sys_user`（用户表）

| 字段 | 类型 | 说明 |
|---|---|---|
| user_id | varchar(50) | 用户工号（如 QD21000115） |
| name | varchar(100) | 姓名 |
| nick_name | varchar(100) | 昵称 |
| role | varchar(20) | 角色 |
| agent | bigint[] | 可访问的 hi_agent_list.id 数组 |
| status | boolean | 启用状态 |
| deleted_at | timestamptz | 软删除时间 |

### 2.2 vlagent 本地数据源

#### `modules`（功能模块表，新增 agent_id 字段）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer | 主键 |
| key | varchar | 模块标识（如 bank-statement），唯一索引 |
| title | varchar | 显示名称 |
| description | varchar | 描述 |
| icon | varchar | 图标名 |
| route | varchar | 前端路由 |
| gradient | varchar | 图标渐变样式 |
| hover_class | varchar | 悬停样式 |
| sort_order | integer | 排序 |
| status | boolean | 启用状态 |
| **agent_id** | **integer, nullable** | **上游 hi_agent_list.id，同步关联键** |
| created_at | datetime | 创建时间 |

**`agent_id` 说明：**
- 存储对应的 `hi_agent_list.id`，作为同步时的匹配依据
- 首次同步时由上游数据自动写入，后续同步通过此字段匹配
- 值为 NULL 的 module 表示未关联上游（本地自定义模块）

#### `user_permissions`（用户权限表，结构不变）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | integer | 主键 |
| user_id | varchar | 用户工号 |
| module | varchar | modules.key |
| created_at | datetime | 创建时间 |

### 2.3 关联关系

```
上游 hi_agent_list              本地 modules               本地 user_permissions
┌──────────────────┐           ┌──────────────────┐        ┌─────────────────────┐
│ id=54  pid=46    │──agent_id─│ key=bank-statement│◄───────│ user_id, module     │
│ id=55  pid=46    │──agent_id─│ key=confirm...    │◄───────│ user_id, module     │
│ ...              │           │ ...              │        │ ...                 │
└──────────────────┘           └──────────────────┘        └─────────────────────┘
         ▲
         │ agent 数组引用
         │
┌──────────────────┐
│ sys_user         │
│ user_id=QD...    │
│ agent={46,54,55} │
└──────────────────┘
```

**核心查询（权限同步时使用）：**

```sql
-- 根据 sys_user.agent 数组，查出该用户有权访问的 modules.key
SELECT key FROM modules WHERE agent_id = ANY(:user_agent_ids)
```

### 2.4 权限映射示例

```
上游数据：
  sys_user: user_id=QD21000115, agent={42, 46, 54, 55, 58}

同步过程：
  1. 包含 46 → 是 vlagent 用户 ✓
  2. agent 与本地 modules.agent_id 取交集：{54, 55, 58}
  3. 查 modules 表：54→bank-statement, 55→confirmation-letter, 58→invoice-recognition

写入 user_permissions：
  (QD21000115, bank-statement)
  (QD21000115, confirmation-letter)
  (QD21000115, invoice-recognition)

前端请求：
  GET /api/permissions/me → ["bank-statement", "confirmation-letter", "invoice-recognition"]
  GET /api/modules        → 3 个模块的完整信息（含 icon、route 等）
```

---

## 3. 技术方案

### 3.1 新增依赖

使用 `apscheduler`（轻量级定时任务库）实现定时同步，无需引入 Redis/Celery 等外部组件。

```
# pyproject.toml 新增
apscheduler>=3.10.0
```

### 3.2 配置项

```python
# config.py 新增
DATABASE_UPSTREAM_URL: str = Field(
    default="",
    description="上游数据库连接 URL（ioa 库）"
)
SYNC_INTERVAL_MINUTES: int = Field(
    default=5,
    description="上游数据同步间隔（分钟）"
)
```

`.env` 示例：
```
DATABASE_UPSTREAM_URL=postgresql+asyncpg://postgres:ioadev123456@10.238.146.99:30432/ioa
SYNC_INTERVAL_MINUTES=5
```

### 3.3 上游数据库连接

在 `database.py` 中新增第二个 engine/session：

```python
# 上游数据库（只读）
upstream_engine = create_async_engine(
    settings.DATABASE_UPSTREAM_URL,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=3,
    pool_recycle=300,
)
UpstreamSessionLocal = sessionmaker(
    upstream_engine, class_=AsyncSession, expire_on_commit=False
)
```

### 3.4 同步模块设计

新增 `src/sync/` 模块：

```
src/sync/
├── __init__.py
├── scheduler.py         # APScheduler 初始化和任务注册
├── sync_modules.py      # hi_agent_list → modules 同步
└── sync_permissions.py  # sys_user → user_permissions 同步
```

---

## 4. 同步逻辑详细设计

### 4.1 模块同步（hi_agent_list → modules）

```
输入：SELECT * FROM hi_agent_list WHERE pid = 46 AND is_delete = false
输出：UPDATE/INSERT modules 表

流程：
1. 查询上游 hi_agent_list WHERE pid=46 AND is_delete=false
2. 查询本地 modules 全部记录，构建 agent_id → Module 的索引
3. 遍历上游结果，按 agent_id 匹配本地 module：
   - 匹配到 → UPDATE（同步 title, description, sort_order, status）
   - 未匹配 → INSERT（agent_id=上游id, title, description, sort_order 从上游取；
                         key, icon, route, gradient, hover_class 使用默认值，需人工补全）
4. 标记缺失：本地有 agent_id 但上游已删除的 → UPDATE status=false
5. 记录同步日志
```

**字段映射规则：**

| modules 字段 | 来源 |
|---|---|
| agent_id | hi_agent_list.id（匹配键） |
| title | hi_agent_list.name |
| description | hi_agent_list.description |
| sort_order | hi_agent_list.sorting |
| status | hi_agent_list.is_show == 1 AND is_delete == false |
| key | 本地不变（首次 INSERT 时需人工指定） |
| icon | 本地不变（首次 INSERT 时需人工指定） |
| route | 本地不变（首次 INSERT 时需人工指定） |
| gradient | 本地不变（首次 INSERT 时需人工指定） |
| hover_class | 本地不变（首次 INSERT 时需人工指定） |

**首次同步特殊处理：**

本地 modules 表已有 7 条 seed 数据（由 `init_db` 写入），首次同步时需要将 `hi_agent_list.id` 写入对应 module 的 `agent_id` 字段。匹配方式：按 `name` 相等匹配（上游 name 与本地 title 一致）。

```
首次同步：
  上游: id=54, name="流水识别"
  本地: key="bank-statement", title="流水识别", agent_id=NULL
  匹配: name == title → SET agent_id=54

后续同步：
  直接按 agent_id 匹配，不再依赖名称
```

### 4.2 权限同步（sys_user → user_permissions）

```
输入：
  - SELECT user_id, agent FROM sys_user WHERE deleted_at IS NULL AND status = true
  - 本地 modules 表的 agent_id 集合
输出：全量替换 user_permissions 表

流程：
1. 从本地 modules 表获取所有有效 agent_id：SELECT agent_id FROM modules WHERE agent_id IS NOT NULL
2. 获取所有活跃用户：SELECT user_id, agent FROM sys_user WHERE deleted_at IS NULL
3. 过滤：只保留 agent 数组中包含 id=46 的用户（有 vlagent 访问权限）
4. 对每个有效用户：
   - 计算 agent 与本地 modules.agent_id 集合的交集
   - 通过 modules 表反查：SELECT key FROM modules WHERE agent_id = ANY(交集)
   - 若交集为空但有 id=46 → 该用户无子模块权限，不写记录
5. 全量替换 user_permissions（在事务中执行）：
   - DELETE FROM user_permissions
   - 批量 INSERT 新权限记录
6. 事务提交，保证原子性
```

**权限决策矩阵：**

| sys_user.agent 包含 | 结果 |
|---|---|
| 含 46 且含子模块 agent_id | 有对应子模块权限 |
| 含 46 但无子模块 agent_id | 无任何子模块权限（空记录） |
| 不含 46 | 不属于 vlagent 用户，不处理 |

### 4.3 同步触发时机

1. **定时同步**：应用启动后按 `SYNC_INTERVAL_MINUTES` 间隔执行
2. **启动同步**：应用启动时立即执行一次
3. **手动触发**：提供 `POST /api/admin/sync` 接口，支持手动触发同步（可选）

### 4.4 同步流程图

```
应用启动
  │
  ├── 立即执行首次同步
  │     ├── sync_modules()     ← hi_agent_list → modules（含首次 agent_id 绑定）
  │     └── sync_permissions() ← sys_user + modules.agent_id → user_permissions
  │
  └── 启动定时调度器
        └── 每 N 分钟
              ├── sync_modules()
              └── sync_permissions()
```

---

## 5. 错误处理与容错

### 5.1 上游库不可用

- 同步任务捕获所有数据库异常，记录日志，不影响 vlagent 正常运行
- 连接池配置 `pool_pre_ping=True`，自动检测断开连接
- 连续失败超过 N 次（可配置）时输出告警日志

### 5.2 同步失败回滚

- 权限同步使用数据库事务：失败时回滚，保留旧数据
- 模块同步逐条处理：单条失败不影响其他模块

### 5.3 数据一致性

- 采用全量同步策略（非增量），每次同步重新计算完整权限集
- 避免增量同步中的遗漏和状态不一致问题

### 5.4 日志

- 每次同步记录：开始时间、结束时间、同步记录数、成功/失败状态
- 使用 Python logging 模块，集成到 vlagent 现有日志体系

---

## 6. 上游数据准备

### 6.1 在 hi_agent_list 中插入子模块记录

```sql
INSERT INTO hi_agent_list (id, name, url, description, pid, sorting, is_delete, is_show, permissions, created_at, updated_at)
VALUES
  (47, '流水识别',       '', 'AI 识别银行流水 PDF，提取交易明细、账户信息和汇总数据',       46, 1, false, 1, false, now(), now()),
  (48, '询证函识别',     '', 'AI 识别银行询证函 PDF，自动提取编号、事务所等关键字段',     46, 2, false, 1, false, now(), now()),
  (49, '文档比对',       '', '逐页对比两份文档，逐行标注新增、删除、修改内容',             46, 3, false, 1, false, now(), now()),
  (50, '询证函格式比对', '', '将询证函与标准模板比对，检查格式是否符合规范',             46, 4, false, 1, false, now(), now()),
  (51, '发票识别',       '', '识别电子发票 PDF 及图片，提取发票号码、金额等信息',         46, 5, false, 1, false, now(), now()),
  (52, '类凭证识别',     '', '识别身份证、银行卡、电子印章等多种凭证类型的关键信息',       46, 6, false, 1, false, now(), now()),
  (53, '通用PDF提取',    '', '自定义提取字段，AI 从任意 PDF 中提取结构化数据',            46, 7, false, 1, false, now(), now());
```

### 6.2 为用户分配权限

```sql
-- 示例：为 QD21000115 分配全部 7 个子模块权限
UPDATE sys_user
SET agent = ARRAY[46, 47, 48, 49, 50, 51, 52, 53]
WHERE user_id = 'QD21000115';
```

---

## 7. 改动清单

### 7.1 新增文件

| 文件 | 说明 |
|---|---|
| `src/sync/__init__.py` | 空文件 |
| `src/sync/sync_modules.py` | 模块同步逻辑 |
| `src/sync/sync_permissions.py` | 权限同步逻辑 |
| `src/sync/scheduler.py` | APScheduler 初始化 |

### 7.2 修改文件

| 文件 | 改动 |
|---|---|
| `pyproject.toml` | 添加 `apscheduler` 依赖 |
| `src/config.py` | 添加 `DATABASE_UPSTREAM_URL`、`SYNC_INTERVAL_MINUTES` 配置项 |
| `src/database.py` | 添加上游数据库 engine 和 session；`init_db` 中 modules seed 逻辑增加 `agent_id` 幂等写入 |
| `src/main.py` | lifespan 中启动/关闭 scheduler |
| `src/modules/models.py` | Module 模型新增 `agent_id` 字段 |
| `.env` | 添加 `DATABASE_UPSTREAM_URL`、`SYNC_INTERVAL_MINUTES` |

### 7.3 不改动

| 范围 | 说明 |
|---|---|
| 前端代码 | API 接口形状不变 |
| `user_permissions` 表结构 | 保持不变 |
| `src/modules/router.py` | 保持不变 |
| `src/permissions/router.py` | 保持不变 |

---

## 8. 后续可扩展

- **管理接口**：`POST /api/admin/sync` 手动触发同步、`GET /api/admin/sync/status` 查看同步状态
- **Webhook**：上游系统变更权限后主动通知 vlagent 触发同步（需上游配合）
- **同步审计日志**：记录每次同步的变更明细，便于排查权限问题
- **新增子模块**：上游 `hi_agent_list` 插入新子模块 → 首次同步时自动创建本地 module 记录 → 人工补全 key/icon/route 等字段
