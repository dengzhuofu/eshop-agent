# ADR 0003：LangGraph 标准目录与原生运行时

日期：2026-07-13
状态：Accepted

## 背景

项目已从单一 Product Launch skeleton 扩展到选品铺货、运营诊断和客服 Routed RAG。当前 `backend/app/agents/graphs/` 的技术分层能够支撑早期 MVP，但 `workflows/product_launch.py` 同时承担图装配、执行、快照、恢复和 trace，且没有使用 LangGraph 原生 checkpointer、store、稳定 `thread_id` 和 interrupt/resume。

用户要求以后端参考项目的每个模块代码和职责作为规范基线，同时为跨境电商全链路、多工作流平台保留扩展能力。

## 决策

1. 后端迁移为 `backend/src/app/` Python 工程。
2. 公共模块遵循参考项目的 `api/app.py`、`api/dependencies.py`、`guardrails`、`models`、`observability`、`persistence`、`prompts`、`schemas`、`services`、`tools` 结构。
3. 每个业务工作流使用独立包，并在包内遵循 `graph.py`、`state.py`、`edges.py`、`nodes/` 结构。
4. `backend/langgraph.json` 分别导出 Product Launch、Operations 和 Support 图。
5. MVP 使用 `InMemorySaver` 和 `InMemoryStore`；生产持久化通过工厂替换，生产配置不完整时 fail fast。
6. Product Launch 迁移为单图 `interrupt()` 与 `Command(resume=...)`，并使用稳定的内部 `thread_id`。
7. Checkpointer 只保存 thread 执行状态；Store 只保存跨 thread 长期记忆；Approval、Trace 和 PublishOperation 保持独立业务事实。
8. API 通过 `dependencies.py` 注入 graph、可信 `RequestContext` 和 repository interfaces。
9. 旧 `backend/app/` 不作为长期兼容层保留；迁移在独立集成分支中一次完成并同步更新测试。
10. `pyproject.toml` 成为唯一依赖真源，并补齐参考项目所示的 README、Dockerfile、脚本、迁移目录和 CI 基线。
11. 请求身份通过 LangGraph `context_schema` 和 `Runtime[GraphRuntimeContext]` 进入节点；repository、ToolExecutor 和 service 在 graph build time 注入节点闭包，不写入 state，也不由节点运行时获取全局单例。
12. `approval_gate` 的 resume value 必须经过确定性状态路由；只有 approved 决策可以进入发布，rejected、expired 和 revoked 进入无副作用终态。
13. MVP 内存 profile 明确限制为单进程单 worker；跨进程 durable、lease/fencing 和崩溃恢复只在 PostgreSQL profile 下承诺和验证。
14. 客服 MVP 固定使用 ACL 预过滤词法检索；交易事实使用七个类型化工具，向量/hybrid 只在评估证明收益后新增。
15. 发布副作用使用 PublishOperation 状态机、provider idempotency key 和 outcome/outbox 同事务契约；未知结果先 reconciliation，禁止盲目重试。

## 原因

- 直接复制单图示例会把多个工作流重新塞入一个 state 和 graph，不能满足全链路平台扩展。
- 只增加顶层兼容门面会继续保留旧目录和职责混杂，不能满足“以示例为准”的要求。
- 工作流内聚既保留示例的模块职责，又隔离不同 state、route、节点和恢复策略。
- 原生 checkpointer 和 interrupt/resume 能展示真正的 durable execution 与 HITL 工程能力。
- 将审批、审计和外部副作用账本独立保存，可以避免把 checkpoint 错误当成业务授权或 exactly-once 保证。
- Runtime Context 与 build-time dependency injection 同时满足 state 可序列化和节点可测试，不需要把服务实例放进 checkpoint。

## 被否决方案

### 方案 A：全部使用顶层单图结构

优点是与示例物理目录最接近。缺点是 Product Launch、Operations 和 Support 会共享过宽 state，节点、路由和测试持续膨胀，因此否决。

### 方案 B：保留 `backend/app/` 并增加 re-export

优点是短期改动小。缺点是形成两套路径，无法真正验证目录规范，也会让后续 Agent 继续向旧目录写代码，因此否决。

### 方案 C：用 LangGraph checkpoint 取代全部业务仓储

Checkpoint 不保存审批者权限事实、业务审计语义或外部副作用 exactly-once 证明，因此否决。

## 后果

### 正向后果

- 每张图的装配、状态、路由和节点边界清晰。
- 可由 `langgraph.json`、LangGraph CLI 或 API 加载和验证多张图。
- 恢复、审批、幂等、租户隔离和状态版本具备明确测试入口。
- 模型、RAG、平台连接器和持久化实现可以独立替换。
- 目录本身能作为后续开发约束，降低大文件和隐式副作用回归。

### 代价

- 合并 Node 16-19 后需要一次较大的 import、fixture 和测试目录迁移。
- 原 snapshot API 与原生 checkpoint 语义不同，需要兼容投影。
- 当前内存 MVP 不保留跨部署 workflow，本次切换前清空演示状态；未来出现持久化 legacy workflow 时必须另写迁移 ADR。
- 真正的发布 exactly-once 仍需要持久化 operation ledger/outbox，不能只依赖 LangGraph。
- 内存 profile 不能用于证明多进程 durable，生产演示需要 PostgreSQL integration profile。

## 实施门禁

- 先修复 Node 16-19 独立评审发现的 Important 问题，再做目录迁移。
- 每个迁移阶段运行全量测试、`git diff --check` 和 graph 加载检查。
- 未解决 Critical 或 Important 评审项时禁止合并。
- 不读取、输出、提交或记录 SiliconFlow API key。

## 详细设计

完整目录、运行时、RAG、安全、测试和迁移设计见：

`docs/superpowers/specs/2026-07-13-langgraph-standard-project-runtime-design.md`
