# EKG Agent Refactor 技术架构与功能报告

## 1. 报告目的与范围

本报告用于完整说明 EKG Agent Refactor 当前版本的整体技术架构、关键执行链路、核心模块职责、已实现功能能力与运行特性。内容基于当前仓库实现状态，面向开发、测试、运维和交付场景。

## 2. 项目定位

EKG Agent Refactor 是面向电子元件管理场景的智能工作流系统，核心目标是将自然语言交互、知识检索、SQL/Python 执行、安全治理、人工审批、变更追踪与版本回滚整合为一条可审计、可追溯、可恢复的业务闭环。

## 3. 总体架构

系统采用分层架构与模块化组合：

- 接口层（FastAPI）
  - 对外提供 Chat、Approval、Admin、Knowledge 四类 API。
  - 提供首页控制台、健康检查、状态查询与 OpenAPI 文档。

- 核心编排层（Workflow）
  - 统一调度 GraphRAG、CodeGen、安全评估、审批、执行、版本化和响应组装。
  - 在写操作完成后触发本体增量更新。

- 知识层（GraphRAG + Ontology）
  - 基于本体图进行检索增强。
  - 支持双层索引（semantic/control）、RAS 迭代检索与自适应停止。

- 执行层（Repository + Sandbox）
  - 负责 SQL 执行、干跑模拟、数据持久化。
  - 通过 SQL 沙箱降低执行风险。

- 治理层（Security + Approval + Versioning）
  - 三层安全防护（pre/during/post）。
  - 高风险操作可转入人工审批。
  - 写操作全量快照支持分支与回滚。

- 适配层（Integrations）
  - 提供与 agent_codex、warehouse-ai 的能力兼容接口。

## 4. 关键技术栈

- Web/API: FastAPI, Uvicorn
- 数据模型: Pydantic v2, pydantic-settings
- 数据存储: SQLite
- 图谱与索引: JSON 本体图 + 内存索引
- 表格导入: openpyxl
- 大模型接入: OpenAI-compatible API
- 配置与环境: .env + BaseSettings

## 5. 主要模块说明

### 5.1 API 路由层

- Chat 路由
  - POST /v1/chat: 同步执行请求。
  - POST /v1/chat/stream: SSE 流式返回。

- Approval 路由
  - GET /v1/approvals: 审批列表。
  - GET /v1/approvals/{ticket_id}: 审批详情（含副驾驶建议）。
  - POST /v1/approvals/{ticket_id}/decision: 通过/拒绝审批。

- Admin 路由
  - 版本浏览、版本树、创建分支、分支切换、回滚。
  - 变更日志与变更解释查询。

- Knowledge 路由
  - 图谱初始化、检索、索引重建、增量更新。

### 5.2 工作流编排（UnifiedWorkflowService）

主编排职责：

1. 接收用户请求并提取上下文。
2. 调用 GraphRAG 获取证据与上下文补充。
3. 调用 CodeGen 生成可执行动作（SQL/Python）。
4. 执行 pre-operation 安全判断。
5. 根据安全结果决定直接执行、阻断或进入审批。
6. 执行 SQL 沙箱静态校验与干跑。
7. 执行真实数据操作并生成版本快照。
8. 写操作后触发本体增量更新。
9. 输出标准化响应（结果、安全摘要、图谱证据、调试信息）。

### 5.3 代码生成（CodeGen）

- 采用“确定性规则优先 + LLM 兜底”的双通道策略。
- 对常见电子元件查询语义内置模板化生成能力。
- 支持型号/厂商等关键词纠错与实体匹配。
- 输出统一动作为 GeneratedAction，便于后续安全与执行模块处理。

### 5.4 知识检索（GraphRAG）

当前检索模式为 RAS 双层迭代：

- semantic 层：关注名称、别名、属性 token 的语义匹配。
- control 层：关注节点类型、关系、入出边与结构线索。
- 迭代策略：多轮 query refinement + 邻域扩展。
- 停止策略：根据信息增益、新节点数量和稳定轮次触发自适应停止。
- 返回内容：上下文摘要、证据节点、调试统计（round stats、stop reason 等）。

### 5.5 安全治理

安全流程包含三阶段：

- pre_operation: 执行前风险判定与策略决策。
- during_operation: 执行过程中检查。
- post_operation: 执行后审计与反馈。

同时支持可选的 LLM 安全代理回调增强建议能力，审计日志写入 data/audit/security_audit.jsonl。

### 5.6 SQL 沙箱

沙箱机制分为两部分：

- 静态策略校验
  - 限制语句数量。
  - 控制语句动词与关键字。
  - 校验可触达表范围。

- 动态干跑模拟
  - 在临时副本上执行 SQL。
  - 验证可执行性与风险，不污染真实数据。

已完成的策略修正：允许 SELECT 中 replace(...) 函数调用，同时保持对 REPLACE INTO / INSERT OR REPLACE 语句的拦截。

### 5.7 审批与审批副驾驶

- 当 pre_operation 判断为 require_human 且未自动放行时，创建审批单。
- 审批状态管理：pending -> approved/rejected -> executed/failed。
- 审批副驾驶输出结构化建议，包括：
  - recommendation / confidence / risk_level / final_decision
  - risk_points / suggested_actions / approver_checklist
  - policy_mappings

### 5.8 版本治理与回滚

- 写操作生成 before/after 快照。
- 每个版本记录 parent_version_id、thread_id、branch、metadata(change_log)。
- 支持：
  - 版本树浏览
  - 分支创建
  - 分支切换（恢复 head）
  - 任意版本回滚

### 5.9 本体增量更新

写操作成功后，系统会自动将 change_log 编织到本体图：

- 新增或更新 ChangeEvent、BranchContext、Actor、DataTable、VersionSnapshot 等节点。
- 建立事件、表、分支、版本之间关系。
- 支持手动接口补录和重建索引，保障知识连续性。

### 5.10 Excel Bootstrap

系统支持通过 Excel 初始化基础数据与图谱：

- 多 sheet 解析
- 头部字段映射与推断
- 原始表重建（excel_*）
- 标准业务表补齐与本体节点边构建

## 6. 数据与持久化设计

持久化介质：

- SQLite 业务库: data/components.db
- 本体图谱: data/ontology_graph.json
- 版本快照目录: data/versions/
- 安全审计日志: data/audit/security_audit.jsonl

运行时内存态（重启丢失）：

- 审批运行时映射
- 部分线程活跃分支运行态

## 7. Web 控制台能力

首页控制台集成多个功能面板：

- 对话请求与响应
- 图谱证据展示
- 安全摘要展示
- 人工审批台
- 版本树与分支操作
- 变更解释器

这使业务用户和工程人员能够在单页面完成“提问 -> 审批 -> 执行 -> 追溯”的闭环操作。

## 8. 已实现功能清单（摘要）

- 自然语言到 SQL/Python 动作生成与执行
- GraphRAG 检索增强与证据回传
- 双层索引 + RAS 迭代 + 自适应停止
- 三层安全治理 + 审计日志
- SQL 沙箱静态校验 + 干跑
- 人工审批与审批副驾驶
- 变更解释器
- 版本树、分支、回滚
- 写后自动本体增量更新
- 知识索引重建与手动增量接口
- Excel 数据引导初始化
- 对外系统兼容适配

## 9. 典型请求链路说明

### 9.1 读请求

1. 用户输入查询。
2. GraphRAG 检索增强上下文。
3. CodeGen 产出 SELECT 动作。
4. pre 安全判断通过。
5. 沙箱校验 + 干跑。
6. 执行查询并返回结果、证据和安全摘要。

### 9.2 写请求（需要审批）

1. 用户提出更新请求。
2. GraphRAG + CodeGen 生成写操作动作。
3. pre 安全判断为 require_human。
4. 创建审批单，返回 pending。
5. 审批人通过后执行写入。
6. 生成 before/after 版本快照。
7. 自动执行本体增量更新。
8. 返回执行结果与审计信息。

## 10. 可运维与可扩展性评价

- 可运维性
  - 有健康检查、状态接口、审计日志与版本追踪。

- 可恢复性
  - 快照与回滚机制完整，支持分支化演进。

- 可扩展性
  - 模块边界清晰，可扩展新的路由、新安全策略、新索引策略和新适配器。

- 可治理性
  - 安全规则、审批机制、变更解释形成治理闭环。

## 11. 当前约束与建议

- 部分运行态信息为内存态，生产环境建议引入持久化审批存储。
- 对高并发场景建议进一步评估 SQLite 锁争用并引入更强后端数据库。
- 对安全策略建议持续做规则细化与误拦截回归测试。
- 对 GraphRAG 建议增加离线评测集以持续优化权重与停止阈值。

## 12. 结论

EKG Agent Refactor 当前版本已具备从“自然语言意图”到“可控执行与可追溯治理”的完整工程闭环，关键创新点集中在：

- 安全与审批融合的执行链路
- 双层 GraphRAG 的可解释检索增强
- 写后自动本体增量更新
- 版本树驱动的可回滚数据治理

系统已达到可演示、可验证、可迭代的阶段，适合作为电子元件管理智能副驾驶的核心底座继续演进。
