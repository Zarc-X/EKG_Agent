# EKG Agent Refactor

本项目是电子元件管理场景下的统一智能工作台，目标是把自然语言交互、图谱检索、SQL/Python 生成执行、安全治理、审批追踪、版本回溯整合到同一条可审计链路。

当前版本已经完成核心架构闭环，并在 Web 控制台中提供端到端可操作能力。

## 当前实现状态总览

已落地能力（可直接使用）：

- 自然语言到数据库操作（读写）
- 图谱增强检索（Graph RAG）并回传证据
- 代码生成双通道（确定性模板优先 + LLM 兜底）
- 操作前/中/后三层安全防护（复用 security_guard）
- SQL 沙箱（静态校验 + 干跑）
- 人工审批流（审批单列表、详情、通过/拒绝、执行态回写）
- 审批副驾驶（结构化建议、风险点、策略映射、建议动作）
- 变更解释器（风险等级、管理摘要、回滚建议、检查清单）
- SQLite 快照版本库（before/after 快照、回滚、分支、头指针）
- 双层图索引（semantic/control）+ RAS 迭代检索 + 自适应停止
- 本体增量更新（写操作后自动入图）
- 手动知识维护接口（增量更新、索引重建）
- Web UI 管理台（聊天、版本树、审批台、变更解释、证据、安全摘要）
- 对外兼容适配器（agent_codex / warehouse-ai）

## 架构分层

- app/api
	- FastAPI 路由层，按 chat/approval/admin/knowledge 分组。
- app/core
	- 主编排 UnifiedWorkflowService。
	- 审批服务、模型定义、安全运行时装配。
- app/codegen
	- GeneratedAction 生成器。
	- 确定性规则、拼写纠错、LLM JSON 生成兜底。
- app/knowledge
	- OntologyStore（JSON 图谱存储）。
	- EntityLinker + GraphRAGService（双层索引 + 迭代检索）。
- app/db
	- ComponentRepository（SQLite 执行与模拟执行）。
	- SqlSandboxPolicy（关键字/语句/触表校验）。
	- SqliteVersionStore（快照、分支、回滚、heads）。
- app/bootstrap
	- Excel 导入与图谱构建（多 sheet、字段映射、原始表重建）。
- app/integrations
	- 与 agent_codex、warehouse-ai 的协议/命令转换适配。
- app/web_ui.py
	- 单页管理控制台 HTML/CSS/JS。

## 端到端执行流程

聊天请求（POST /v1/chat）默认路径：

1. 用户请求进入 UnifiedWorkflowService.process_chat。
2. GraphRAG 检索，返回 context + evidence。
3. CodeGen 生成 SQL/Python 与执行摘要。
4. 安全 pre_operation 判断：allow / require_human / block。
5. 若 require_human 且未 auto_approve：创建审批单并挂起执行。
6. 若继续执行：
	 - SQL 沙箱静态校验。
	 - SQL 沙箱干跑 simulate。
	 - 安全 during_operation。
	 - 正式执行 SQL。
7. 写操作时：
	 - before 快照。
	 - after 快照（携带 change_log）。
	 - 自动触发本体增量更新（事件、表、版本关系入图）。
8. 安全 post_operation，返回标准化响应（含安全摘要、证据、执行结果）。

审批路径：

- /v1/approvals/{ticket_id}/decision 批准后执行 execute_approved。
- 拒绝时直接返回 blocked，不执行 SQL。

## 核心能力细节

### 1) CodeGen 与语义纠错

- 优先走确定性快捷路径：库存、厂商、采购日期、采购单号相关查询。
- 支持型号与厂商拼写纠错（SequenceMatcher + 别名索引 + 阈值）。
- 无法确定时可使用 LLM 生成结构化 JSON 动作。
- 输出统一为 GeneratedAction：operation_type/sql/params/requires_write/estimated_rows/summary/python_code。

### 2) 安全治理

- 三层安全（pre/during/post）通过 security_guard 注入。
- 可选安全代理回调（LLM）参与建议与置信度评估。
- 审计日志落盘到 data/audit/security_audit.jsonl。

### 3) SQL 沙箱

- 静态校验：语句数、动词白名单、关键字黑名单、触表范围。
- 干跑执行：复制 DB 到临时文件执行后回滚，不污染真实库。
- 已修复 replace() 函数误拦截问题：
	- 允许 SELECT 中 replace(...) 调用。
	- 仍拦截 REPLACE INTO / INSERT OR REPLACE 等写语句。

### 4) 审批与审批副驾驶

- 审批单生命周期：pending -> approved/rejected -> executed/failed。
- 审批 payload 包含 action/request/graph_context/evidence/pre。
- approval_copilot 提供：
	- recommendation/confidence/final_decision/risk_level。
	- risk_points/suggested_actions/approver_checklist。
	- policy_mappings（策略项逐条映射状态）。

### 5) 版本治理与变更解释

- 写操作自动生成 before/after 快照。
- change_log 写入版本 metadata。
- 支持按 thread/branch 浏览版本树与 heads。
- 支持创建分支、切换分支、回滚到任意版本。
- 变更解释器输出：
	- risk_level（low/medium/high/critical/unknown）
	- impact_scope、management_summary、rollback_recommendation、checks

### 6) 图谱检索与知识更新

- GraphRAG 检索模式：ras_iterative_dual_layer。
- 双层索引：
	- semantic 层（节点名称、别名、属性 token）
	- control 层（类型、关系、入出边、结构线索）
- 多轮 query refinement + 邻域扩展 + gain/new_nodes 自适应停止。
- 写后自动本体增量更新：
	- 新增 ChangeEvent / BranchContext / Actor / DataTable / VersionSnapshot 节点与关系。
- 提供手动接口重建索引和补录增量。

### 7) 前端控制台

首页包含以下面板：

- 聊天交互区（请求/响应）
- 版本树与分支（创建/切换/回滚）
- 人工审批台（列表/详情/通过/拒绝）
- 变更解释器（风险与回滚建议）
- 图谱证据
- 安全摘要

## API 一览

### 系统

- GET /
- GET /status
- GET /health
- GET /docs

### Chat

- POST /v1/chat
- POST /v1/chat/stream

### Approval

- GET /v1/approvals
- GET /v1/approvals/{ticket_id}
- POST /v1/approvals/{ticket_id}/decision

### Admin

- GET /v1/admin/versions
- GET /v1/admin/version-tree
- POST /v1/admin/branches
- POST /v1/admin/checkout
- POST /v1/admin/rollback/{version_id}
- GET /v1/admin/change-logs
- GET /v1/admin/change-explanations

### Knowledge

- POST /v1/knowledge/bootstrap
- GET /v1/knowledge/search
- POST /v1/knowledge/index/rebuild
- POST /v1/knowledge/incremental-update

## 数据落盘与状态

- SQLite 主库：data/components.db
	- components / inventory / bom
	- excel_sheet_registry + 动态 excel_* 原始表（启用 Excel 导入时）
- 本体图谱：data/ontology_graph.json
- 版本索引与快照：data/versions/versions_index.json + *.db
- 安全审计：data/audit/security_audit.jsonl

说明：

- 审批单与当前线程活跃分支映射属于内存态，服务重启后会重置。
- 版本与图谱与审计属于持久态，会保留在 data 目录。

## 配置项（.env）

关键配置（详见 .env.example）：

- 服务：APP_NAME / APP_ENV / APP_HOST / APP_PORT
- 数据路径：SQLITE_DB_PATH / ONTOLOGY_JSON_PATH / VERSION_DIR / SECURITY_AUDIT_LOG
- GraphRAG：
	- GRAPH_RAG_TOP_K
	- GRAPH_RAG_ITERATIONS
	- GRAPH_RAG_ITERATION_TOP_K
	- GRAPH_RAG_MAX_QUERY_TERMS
	- GRAPH_RAG_SEMANTIC_WEIGHT
	- GRAPH_RAG_CONTROL_WEIGHT
	- GRAPH_RAG_ADAPTIVE_STOP_ENABLED
	- GRAPH_RAG_ADAPTIVE_MIN_GAIN
	- GRAPH_RAG_ADAPTIVE_MIN_NEW_NODES
	- GRAPH_RAG_ADAPTIVE_STABLE_ROUNDS
- Sandbox：SQL_SANDBOX_ENABLED / SQL_SANDBOX_MAX_STATEMENTS
- Excel 导入：EXCEL_BOOTSTRAP_ENABLED / EXCEL_FILE_PATH
- LLM：LLM_ENABLED / LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / LLM_TIMEOUT_S / LLM_TEMPERATURE / LLM_USE_FOR_SAFE_AGENT

## 快速启动

1. 安装依赖

```bash
pip install -e .
```

2. 准备配置

```bash
cp .env.example .env
```

3. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

4. 打开控制台

```text
http://127.0.0.1:8010/
```

## 最小验证建议

- 语法校验

```bash
python -m compileall -q app
```

- 关键链路检查
	- 读请求：确认 evidence 与安全摘要返回。
	- 写请求：确认审批/执行/版本快照/change_log。
	- 变更解释：确认 /v1/admin/change-explanations 可读。
	- 知识增量：确认 /v1/knowledge/incremental-update 与 /v1/knowledge/index/rebuild 可用。
