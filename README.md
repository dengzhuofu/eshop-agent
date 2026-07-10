# Eshop Agent

跨境电商全链路 Agent 平台。MVP 阶段先使用多平台模拟适配层，重点展示 Agent 工作流、工具边界、人工审批、风险控制、可观测性和评估体系。

## Current Scope

第一阶段先实现后端基础能力：

- FastAPI 服务骨架
- LangGraph-oriented agent directory contract
- SiliconFlow-compatible 模型配置
- Mock Amazon / Shopify / TikTok Shop adapter
- 工具注册中心和风险元数据
- Agent profile boundaries and security isolation checks
- 确定性利润、供应商和风险服务
- 最小 workflow preview API

## Local Backend

```powershell
cd backend
python -m pip install -r requirements.txt
python -m pytest -v
python -m uvicorn app.main:app --reload
```

## Environment

真实 API key 只放在本地 `.env` 或部署平台 secret 中，不写入代码仓库。

See `.env.example` for supported variables.

## Implemented API

```text
GET  /health
GET  /agents/profiles
POST /agents/access-check
GET  /marketplaces/{marketplace}/rules
POST /workflows
```

Example workflow request:

```json
{
  "product_idea": "foldable under-bed storage organizer",
  "target_marketplaces": ["amazon", "shopify", "tiktok_shop"],
  "target_price": 29.99,
  "risk_preference": "balanced"
}
```

The current workflow endpoint returns a deterministic preview with profit estimate, marketplace listing validations, and approval requirement metadata. It does not publish to real platforms.

## Agent Directory Contract

后端按 LangGraph 后续开发需要保留这些目录边界：

```text
backend/app/agents/
  profiles.py              # Agent 角色、可调用工具、风险边界
  graphs/
    state.py               # LangGraph state 结构
    nodes/                 # 节点契约；节点函数后续放这里
    routes/                # route / edge 决策；不得执行副作用
  mcp/                     # MCP connector 元数据；只保存 secret 环境变量名
  skills/                  # Agent skill 元数据；按 Agent role 授权
  prompts/                 # Prompt 元数据；必须版本化并声明上下文边界
  checkpoints/             # Checkpoint 和 human-in-the-loop interrupt 策略
  observability/           # Trace event schema
  evaluation/              # Agent 评估场景注册
  memory/                  # workflow / tenant / global memory 边界
backend/app/tools/         # 后端受控工具注册中心
backend/app/security/      # Agent 边界、租户隔离、审批和 secret 拦截
```

原则：

- Agent 不直接访问数据库、密钥或平台 adapter。
- Agent 只能请求 `ToolRegistry` 中注册过的工具。
- 高风险和关键风险工具必须经过审批。
- 跨租户访问会被拒绝。
- route 函数只决定下一步，不执行业务副作用。
- MCP connector 只记录 secret 环境变量名，不保存 secret 值。
- prompt 必须版本化，并声明 required / forbidden context keys。
- memory 必须区分 workflow、tenant、global 作用域，默认禁止跨租户读。
- observability 事件必须保留 workflow、tenant、agent 和事件类型。

## Progress Logs

每完成一个开发节点，都会在 `docs/progress/` 下生成总结日志，记录目标、完成内容、验证命令、提交号和下一节点。

Current nodes:

- Node 01: repository bootstrap and health API
- Node 02: SiliconFlow-compatible model configuration
- Node 03: mock marketplace adapters
- Node 04: deterministic business services
- Node 05: tool registry and workflow preview API
- Node 06: verification and GitHub push
- Node 07: agent boundaries, security isolation, and LangGraph directory contract

## Product Document

中文 PRD 位于：

`outputs/跨境电商全链路Agent平台-PRD.md`
