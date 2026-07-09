# Eshop Agent

跨境电商全链路 Agent 平台。MVP 阶段先使用多平台模拟适配层，重点展示 Agent 工作流、工具边界、人工审批、风险控制、可观测性和评估体系。

## Current Scope

第一阶段先实现后端基础能力：

- FastAPI 服务骨架
- SiliconFlow-compatible 模型配置
- Mock Amazon / Shopify / TikTok Shop adapter
- 工具注册中心和风险元数据
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

## Progress Logs

每完成一个开发节点，都会在 `docs/progress/` 下生成总结日志，记录目标、完成内容、验证命令、提交号和下一节点。

Current nodes:

- Node 01: repository bootstrap and health API
- Node 02: SiliconFlow-compatible model configuration
- Node 03: mock marketplace adapters
- Node 04: deterministic business services
- Node 05: tool registry and workflow preview API

## Product Document

中文 PRD 位于：

`outputs/跨境电商全链路Agent平台-PRD.md`
