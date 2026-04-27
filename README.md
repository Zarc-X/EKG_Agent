# EKG Agent Refactor

这是一个独立的新目录，用于整合并重构现有能力，目标是实现：
- 前端自然语言交互
- 电子元件本体图谱 + 图RAG
- 基于用户需求生成并执行数据库管理代码（SQL/Python片段）
- 操作前/中/后三层安全防护
- SQL 沙箱静态校验 + 干跑执行（中层防护）
- 审批、审计、版本追溯与回滚
- 分支化版本树（类似 Git 头指针）与线程级切换
- 与现有仓库（agent_codex、warehouse-ai）接口兼容

## 快速启动

1. 安装依赖

```bash
pip install -e .
```

2. 配置环境变量

```bash
cp .env.example .env
```

3. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

4. 打开浏览器访问

```bash
http://127.0.0.1:8010/
```

说明：
- `/` 为可交互网页控制台（聊天 + 安全摘要 + 图谱证据）
- `/` 左侧新增版本树与分支操作面板（创建分支、切换、回滚）
- `/status` 返回服务状态 JSON
- `/docs` 为 OpenAPI 文档

## 主要接口

- `POST /v1/chat`：同步对话执行
- `POST /v1/chat/stream`：SSE 流式执行
- `GET /v1/approvals`：审批单查询
- `POST /v1/approvals/{ticket_id}/decision`：审批通过/拒绝
- `GET /v1/knowledge/search`：图谱检索
- `POST /v1/knowledge/bootstrap`：初始化图谱/样例数据
- `GET /v1/admin/versions`：版本列表
- `GET /v1/admin/version-tree`：按线程查看版本树
- `GET /v1/admin/change-logs`：按线程/分支查看结构化修改记录
- `POST /v1/admin/branches`：创建分支
- `POST /v1/admin/checkout`：切换分支并恢复分支头
- `POST /v1/admin/rollback/{version_id}`：回滚

## 架构分层

- `app/api`：接口层（前端调用）
- `app/core`：流程编排、安全审批、运行时状态
- `app/knowledge`：本体图谱管理、实体链接、图RAG
- `app/codegen`：代码生成（SQL + Python片段）
- `app/db`：数据库执行、SQL 沙箱、版本树快照
- `app/integrations`：对接 agent_codex / warehouse-ai 的适配器
