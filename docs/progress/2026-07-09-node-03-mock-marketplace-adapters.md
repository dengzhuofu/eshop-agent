# 节点 03：领域模型与多平台 Mock Adapter

时间：2026-07-09  
提交：`8b527ec`  
状态：已完成

## 本节点目标

- 建立跨境电商平台适配层的基础领域模型。
- 实现 Amazon-like、Shopify-like、TikTokShop-like 三个 mock marketplace adapter。
- 用测试证明不同平台规则被隔离在 adapter 层，Agent 后续不直接处理平台差异。

## 已完成内容

- 新增 `backend/app/domain/enums.py`：
  - `Marketplace`
  - `RiskLevel`
  - `WorkflowState`
  - `ApprovalStatus`
- 新增 `backend/app/domain/schemas.py`：
  - `ListingDraft`
  - `ValidationIssue`
  - `ValidationResult`
  - `PublishResult`
- 新增 `backend/app/adapters/base.py`，定义 `MarketplaceAdapter` 协议。
- 新增 `backend/app/adapters/mock_marketplaces.py`：
  - `MockAmazonAdapter`
  - `MockShopifyAdapter`
  - `MockTikTokShopAdapter`
  - `get_mock_adapter`

## 平台规则差异

- MockAmazonAdapter：
  - 标题长度不超过 200 字符。
  - 至少需要 3 条 bullet points。
  - 需要类目字段。
  - 检查无证据营销声明。
- MockShopifyAdapter：
  - 标题长度不超过 255 字符。
  - 更灵活，不强制 bullet points。
  - 需要类目字段。
- MockTikTokShopAdapter：
  - 标题长度不超过 120 字符。
  - 需要 `video_hook`。
  - 对 `guaranteed`、`perfect results` 等营销声明更敏感。

## 验证记录

命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

结果：

- 配置测试通过。
- 健康检查测试通过。
- 6 个 marketplace adapter 测试通过。
- 总计 `10 passed`。

## 重要决策

- 平台差异先放在 mock adapter 层，未来接真实 Amazon、Shopify、TikTok Shop API 时可以替换 adapter 实现。
- `publish_listing` 即使是 mock，也使用 `idempotency_key` 生成稳定 listing ID，用来体现生产中的幂等设计。
- Listing 校验是确定性逻辑，不依赖 LLM 输出。

## 下一节点

节点 04：实现利润测算、供应商评分和风险分类等确定性业务服务，为后续 Agent 决策提供可靠工具。
