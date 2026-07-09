# PRD：跨境电商全链路 Agent 平台

版本：0.1  
状态：MVP 开发前草案  
日期：2026-07-09  
主要目标：打造一个面向 Agent 工程师求职的生产化作品集项目

## 1. 项目概述

本项目是一个面向中小跨境卖家的全链路电商 Agent 平台。MVP 阶段先采用“多平台模拟适配层”，暂不直接接入真实 Amazon、Shopify、TikTok Shop 等卖家账号，但整体架构会按照未来真实平台接入的要求来设计。

平台覆盖从选品机会发现、利润测算、供应商评估、多平台 Listing 生成、本地化、风险审核、人工审批、模拟铺货、运营监控、客服售后到复盘优化的完整链路。

这个项目的重点不是做一个聊天机器人，而是做一个小型生产系统：Agent 只能通过受控工具执行动作，高风险操作必须人工审批，每一步决策都有证据链、工具日志、评估结果和审计记录，并且工作流可以回放和复现。

## 2. 产品定位

### 2.1 产品名称

暂定名称：Cross-Border CommerceOps Agent

中文名：跨境电商智能运营 Agent 平台

### 2.2 一句话介绍

一个面向跨境卖家的 Agent 化运营平台，帮助卖家完成从选品、利润测算、供应商评估、多平台铺货、本地化运营、客服售后到复盘优化的全链路工作。

### 2.3 目标用户

- 同时运营多个跨境平台的中小卖家。
- 缺少专门选品、运营、客服、供应链团队的小型商家。
- 希望将重复性运营流程标准化、自动化的电商团队。
- 想要用 AI 辅助业务决策，但仍需要保留人工审批和风险控制的团队。

### 2.4 求职作品集目标

这个项目要重点展示以下能力：

- Agent 工作流设计，而不是单次 LLM 调用。
- 工具调用、工具注册、权限控制和风险分级。
- 多 Agent 协作与职责边界划分。
- 多平台适配层设计，隔离不同平台规则。
- Human-in-the-loop 人工审批机制。
- Agent 可观测性：trace、工具调用、token 成本、失败原因、延迟。
- Agent 评估体系：Listing 质量、证据完整性、客服安全性、流程成功率。
- 生产化意识：异步任务、状态机、幂等性、重试、数据隔离、审计日志、版本管理。

## 3. 背景与问题

跨境电商卖家通常要同时处理选品、竞品分析、供应商比较、利润测算、商品上架、本地化、库存监控、订单处理、客服售后和复盘优化。这些流程重复性强，但风险也很高。

如果自动化做得不好，可能会出现：

- 发布夸大或违规的商品描述。
- 错误定价导致亏损。
- 选择交付风险高的供应商。
- 在没有人工确认的情况下错误退款。
- 根据不充分证据做出选品或运营判断。
- 不同平台规则混在一起，导致上架失败。

普通 AI 聊天工具可以生成文案或建议，但通常缺少：

- 平台级工具边界。
- 可追踪的证据链。
- 高风险动作审批机制。
- 工具权限、风险等级和审计日志。
- 可重复执行、可监控、可回放的 Agent 工作流。
- 能够判断 Agent 输出质量的评估体系。

本项目的核心思路是：**把 Agent 放进一个受控的电商运营系统里，而不是让 Agent 自由地聊天或直接操作外部系统。**

## 4. 目标与非目标

### 4.1 MVP 目标

- 打通一条完整的跨境电商 Agent 工作流：选品 → 利润测算 → 供应商评估 → Listing 生成 → 风险审核 → 人工审批 → 模拟铺货 → 运营监控 → 客服售后 → 复盘。
- 支持多个模拟平台适配器，并体现不同平台的字段、规则和费用差异。
- 让 Agent 通过受控工具完成研究、计算、生成、校验、发布、查询订单和客服回复等动作。
- 对高风险操作强制人工审批，例如发布商品、改价格、发优惠券、退款、下架商品。
- 记录 Agent trace、工具调用、审批记录、评估结果、错误日志和审计日志。
- 提供前端界面，用于启动工作流、查看进度、审批动作、查看 Listing、监控运营数据和调试 Agent。
- 架构上预留未来接入 Amazon、Shopify、TikTok Shop、WooCommerce 等真实平台的空间。

### 4.2 MVP 非目标

- 第一版不直接连接真实卖家账号。
- 第一版不执行真实资金相关操作，例如真实退款、真实发券、真实广告投放。
- 不做完整 ERP、WMS、CRM 或广告投放系统。
- 不追求完美销量预测模型。
- 不支持所有国家、语言、类目和平台规则。
- 不让 Agent 替代人类做最终高风险商业决策。

### 4.3 后续目标

- 接入真实平台 API。
- 接入真实商品、订单、库存、评论和广告数据。
- 支持 CSV / Excel / ERP 导入。
- 支持多租户、团队协作、角色权限和计费。
- 建立更完整的 Agent 评估数据集和回归测试体系。
- 支持事件驱动的持续监控，例如订单、库存、差评、转化率和退款异常。

## 5. MVP 范围

### 5.1 MVP 主工作流

第一期重点实现一条完整主线：

1. 用户创建一个跨境选品和铺货任务。
2. Product Research Agent 分析模拟趋势数据、竞品商品、评论痛点和价格带。
3. Profit Analyst Agent 计算采购价、运费、关税、平台佣金、广告成本、退货风险、毛利和盈亏平衡点。
4. Supplier Agent 对候选供应商进行评分，比较价格、MOQ、交期、质量风险和履约能力。
5. Listing Agent 为不同平台生成 Listing 草稿。
6. Localization Agent 根据目标国家和语言做本地化调整。
7. Risk & Review Agent 检查利润风险、夸大宣传、缺失字段、违规声明和平台规则冲突。
8. 人工审核 Listing 和发布动作。
9. Marketplace Adapter 执行模拟发布。
10. Ops Agent 监控模拟曝光、点击、转化、订单、库存、评论和退货信号。
11. Customer Support Agent 针对模拟客服工单生成回复草稿。
12. 系统生成复盘报告，说明本次选品和铺货流程中的成功点、风险点和后续优化建议。

### 5.2 MVP 支持的模拟平台

第一期实现三个模拟平台适配器：

- MockAmazonAdapter：模拟 Amazon 类平台，规则更严格，包含标题长度、五点描述、类目属性、平台佣金、FBA 类履约假设。
- MockShopifyAdapter：模拟 Shopify 独立站，商品页更灵活，包含 SEO 字段、库存位置、内容区块和更自由的发布流程。
- MockTikTokShopAdapter：模拟 TikTok Shop 类平台，强调短内容、视频卖点、达人内容表达和更严格的营销声明检查。

三个适配器实现相同接口，但内部规则不同。

### 5.3 MVP 商品类目

建议 MVP 只支持 2-3 个相对安全、规则可控的类目：

- 家居收纳类。
- 宠物配件类。
- 健身或健康生活配件类。

MVP 阶段避免高合规风险类目，例如食品、保健品、医疗器械、儿童安全用品、化妆品、电池和强监管电子产品。

## 6. 用户角色与使用场景

### 6.1 商家运营人员

目标：快速判断一个商品是否值得做，并生成可执行的铺货方案。

关注点：

- 是否有市场需求。
- 是否有足够利润。
- 供应商是否可靠。
- Listing 是否足够好。
- 是否值得进入下一步测试。

核心操作：

- 创建选品任务。
- 查看机会评分和利润测算。
- 比较供应商。
- 审核 Listing。
- 查看模拟铺货后的运营数据。

### 6.2 电商运营负责人

目标：掌握流程质量和风险。

关注点：

- Agent 是否按流程执行。
- 高风险动作是否经过审批。
- 失败任务是否可恢复。
- 业务判断是否有证据。
- 团队是否能复盘。

核心操作：

- 查看所有工作流。
- 查看 Agent 决策和工具调用。
- 审批发布、改价、退款等动作。
- 查看错误、重试和审计日志。
- 对比不同工作流的评估分数。

### 6.3 客服人员

目标：用 Agent 辅助处理订单、物流、退款和差评，但保留人工确认。

核心操作：

- 打开客服工单。
- 让 Agent 查询订单和物流状态。
- 查看回复草稿。
- 审核退款或补偿建议。
- 修改后发送回复。

### 6.4 技术面试官

面试官希望确认这不是简单 Prompt Demo，而是一个真实 Agent 工程项目。

项目需要能展示：

- 清晰的 Agent 工作流图。
- Typed tools 和工具权限。
- 多平台 adapter 抽象。
- 审批中心和审计日志。
- 可观测性面板。
- Agent 评估体系。
- 失败恢复和工作流回放。

## 7. 产品需求

### 7.1 工作流创建

用户可以创建一个跨境商品启动任务，输入：

- 商品想法或关键词。
- 目标平台。
- 目标国家或语言地区。
- 商品类目。
- 目标价格区间。
- 可选供应商信息。
- 风险偏好：保守、平衡、激进。

验收标准：

- 系统创建唯一 workflow_id。
- 工作流进入可见状态机。
- 用户可以逐步查看 Agent 执行进度。
- 工作流中断后可以恢复。

### 7.2 选品机会分析

系统分析模拟趋势数据、竞品数据、价格分布和评论痛点。

MVP 输入：

- 模拟趋势记录。
- 模拟竞品商品记录。
- 模拟评论片段。
- 模拟关键词数据。

输出：

- 机会评分。
- 需求判断依据。
- 价格带分析。
- 竞品总结。
- 评论痛点。
- 推荐定位。
- 证据引用。

验收标准：

- 每个重要建议都链接到 mock evidence 记录。
- Agent 能区分事实、推断和假设。
- 数据缺失时必须明确说明。

### 7.3 利润测算

系统计算商品预计盈利能力。

输入：

- 供应商单价。
- MOQ。
- 国际运费。
- 关税和税费假设。
- 平台佣金。
- 支付手续费。
- 履约费用。
- 广告成本假设。
- 退货率假设。

输出：

- 到岸成本。
- 毛利率。
- 贡献利润。
- 盈亏平衡售价。
- 广告成本和退货率敏感性分析。
- 利润风险评分。

验收标准：

- 数学计算由确定性服务完成，不由 LLM 在文本里自由计算。
- Agent 可以用业务语言解释结果。
- 所有假设都被保存并可查看。

### 7.4 供应商评估

系统对候选供应商进行评分。

输入：

- 单价。
- MOQ。
- 交期。
- 质量评分。
- 历史缺陷率。
- 响应速度。
- 所在地区。
- 认证或认证缺失情况。

输出：

- 供应商排序。
- 风险说明。
- 推荐供应商。
- 备选供应商。
- 下单前需要追问供应商的问题。

验收标准：

- 供应商评分由透明公式计算。
- LLM 可以总结和解释，但数字评分逻辑必须可检查。
- 高风险供应商必须被标记。

### 7.5 Listing 生成

系统为不同平台生成商品 Listing 草稿。

每个平台输出：

- 标题。
- 简短描述。
- 五点描述或卖点列表。
- 长描述。
- SEO 关键词。
- 商品属性。
- 变体结构。
- 图片需求 brief。
- 合规提示。
- 本地化说明。

验收标准：

- Listing 草稿符合对应 adapter 的字段限制。
- 夸大或无证据声明会被标记或移除。
- 不同平台生成的 Listing 结构不同。
- Listing 版本在审批前被保存。

### 7.6 本地化

系统根据目标市场调整 Listing。

MVP 本地化能力：

- 语言适配。
- 尺寸、重量、单位换算。
- 表达语气调整。
- 国家或地区用语调整。
- 声明和免责声明检查。

验收标准：

- 本地化内容关联原始 Listing 版本。
- 用户可以查看本地化改动。
- 风险声明在审批前高亮。

### 7.7 风险审核与 Guardrails

系统在执行前检查风险。

风险检查项：

- 利润率低于阈值。
- 退货率假设过高。
- 商品描述包含无证据声明。
- 平台必填属性缺失。
- 折扣或价格策略过于激进。
- 供应商质量风险。
- 类目限制风险。
- 潜在商标或知识产权风险。
- 退款或补偿超出策略阈值。

验收标准：

- 每个工作流都有风险报告。
- 高风险发现会阻止自动执行。
- 用户能看到为什么需要审批。

### 7.8 人工审批

以下操作必须显式审批：

- 发布 Listing。
- 修改价格。
- 应用促销或优惠券。
- 发起退款。
- 发放补偿。
- 下架商品。
- 修改库存预留。

审批记录包括：

- 请求动作。
- 请求来源。
- 涉及工具和 adapter。
- 输入 payload。
- 风险等级。
- Agent 理由。
- 审批人决策。
- 时间戳。

验收标准：

- 高风险动作没有审批不能执行。
- 被拒绝的动作要记录拒绝原因。
- 已批准动作进入不可变审计记录。

### 7.9 模拟铺货

系统通过 mock adapter 发布已批准的 Listing。

行为：

- 校验 Listing payload。
- 返回模拟平台 listing_id。
- 记录发布状态。
- 模拟平台字段错误、限流和临时失败。

验收标准：

- 同一个发布请求可以通过 idempotency_key 安全重试。
- 校验错误对用户和 Agent 可见。
- 系统可以从临时失败中恢复。

### 7.10 运营监控

系统在模拟发布后监控商品表现。

指标：

- 曝光。
- 点击。
- 转化率。
- 订单。
- 收入。
- 库存。
- 评论评分。
- 退货信号。
- 客服工单量。

输出：

- 表现总结。
- 异常检测。
- 下一步行动建议。
- 改价、优化 Listing、补货或客服策略建议。

验收标准：

- 建议必须引用已观测指标。
- 高风险优化动作必须审批。
- 监控结果与 Listing 版本关联。

### 7.11 客服售后

系统基于订单、物流、商品和政策数据生成客服回复草稿。

支持工单类型：

- 订单在哪里。
- 商品不符合预期。
- 退货请求。
- 退款请求。
- 差评回复。

客服 Agent 应该接入 RAG，但 RAG 只负责静态或半静态知识，不负责实时交易事实。

RAG 适用知识：

- 店铺退换货政策。
- 平台售后规则。
- 商品说明书。
- 尺码表、材质说明、安装说明。
- 常见问题 FAQ。
- 物流时效说明。
- 保修政策。
- 多语言客服话术。
- 差评处理规范。

必须走业务工具的数据：

- 订单状态。
- 物流轨迹。
- 支付状态。
- 退款金额。
- 库存状态。
- 优惠券状态。
- 客户历史工单。

客服 Agent 的回答流程：

1. 识别用户问题类型：物流、退款、退货、商品咨询、差评、投诉升级。
2. 查询订单、物流、退款等实时工具。
3. 检索 RAG 知识库，获取政策、商品说明和客服话术。
4. 组合实时数据和检索证据生成回复草稿。
5. Risk & Review Agent 检查是否存在编造物流、过度承诺、违规补偿或不符合政策的问题。
6. 中高风险回复进入人工审核。

验收标准：

- 回复必须基于订单和政策数据。
- 退款和补偿必须审批。
- Agent 不能编造物流状态。
- 用户可以编辑后再发送。
- 涉及政策、商品说明或 FAQ 的回复必须带来源引用。
- 检索不到依据时，Agent 必须说明缺少依据并请求人工处理，不能自行编造。

### 7.12 复盘报告

工作流结束后，系统生成复盘报告。

内容：

- 选品机会总结。
- 最终决策和理由。
- 已发布的 Listing ID。
- 关键风险。
- 发布后的表现。
- 后续优化建议。
- 下一轮实验建议。

验收标准：

- 复盘基于已保存的工作流状态生成。
- 报告包含 trace、证据、审批和评估结果链接。

## 8. Agent 系统设计

### 8.1 Agent 角色

Product Research Agent：

- 发现选品机会。
- 总结需求、竞品缺口和评论痛点。
- 输出必须附带证据 ID。

Profit Analyst Agent：

- 调用确定性计算工具。
- 解释利润和风险。
- 不在自然语言里做不可追踪计算。

Supplier Agent：

- 评估供应商。
- 标记供应链风险。
- 推荐主供应商和备选供应商。

Listing Agent：

- 生成平台特定 Listing。
- 使用平台规则和商品事实。
- 避免无证据声明。

Localization Agent：

- 根据目标市场本地化 Listing。
- 检查语言、单位、文化表达和合规提示。

Ops Agent：

- 监控运营指标。
- 发现异常。
- 提出运营动作建议。

Customer Support Agent：

- 生成客服回复草稿。
- 查询订单、物流和政策工具。
- 对风险工单进行升级。

Risk & Review Agent：

- 评估输出和动作风险。
- 给出风险等级。
- 阻止不安全执行。

Supervisor Agent：

- 管理工作流状态。
- 决定下一步。
- 调度专业 Agent。
- 在需要时创建审批请求。

### 8.2 Agent 边界规则

- Agent 不直接访问数据库表。
- Agent 只能通过 typed tools 执行动作。
- 工具层负责权限、校验、幂等性和审计。
- 数学计算和规则检查放在确定性服务中。
- 高风险动作必须经过审批。
- 每次工具调用都要带上 tenant_id、workflow_id、actor_id、trace_id，写操作还要带 idempotency_key。

### 8.3 工作流状态机

推荐状态：

- draft：草稿。
- queued：已入队。
- researching：选品研究中。
- analyzing_profit：利润分析中。
- evaluating_suppliers：供应商评估中。
- drafting_listings：Listing 生成中。
- localizing：本地化中。
- reviewing_risk：风险审核中。
- awaiting_approval：等待审批。
- executing：执行中。
- monitoring：监控中。
- handling_support：处理客服中。
- retrospective：复盘中。
- completed：完成。
- failed：失败。
- cancelled：取消。

每次状态变化都必须显式持久化。

### 8.4 失败处理

失败类型：

- 工具参数校验失败。
- 平台 adapter 返回错误。
- LLM 输出不符合 schema。
- 缺少证据。
- 缺少计算输入。
- 审批被拒绝。
- 队列超时。
- 模型或外部服务限流。

恢复策略：

- 临时错误使用指数退避重试。
- schema 错误让 Agent 修复结构化输出。
- 缺少业务输入时暂停并请求用户补充。
- 审批拒绝时工作流进入 blocked 或 reroute 状态。
- 保留已有中间结果、trace 和错误信息。

## 9. 工具与平台适配层架构

### 9.1 工具注册中心

每个工具定义包含：

- 工具名称。
- 工具描述。
- 输入 schema。
- 输出 schema。
- 风险等级。
- 所需权限。
- 是否需要幂等。
- 超时时间。
- 重试策略。
- 审计策略。
- 是否需要人工审批。

### 9.2 核心工具分类

研究类工具：

- search_market_trends
- get_competitor_products
- get_review_pain_points
- get_keyword_metrics

利润类工具：

- estimate_landed_cost
- calculate_marketplace_fees
- calculate_break_even_price
- run_margin_sensitivity

供应商类工具：

- list_supplier_candidates
- score_supplier
- compare_suppliers

Listing 类工具：

- create_listing_draft
- validate_listing
- localize_listing
- generate_image_brief

平台类工具：

- publish_listing
- update_price
- update_inventory
- get_orders
- get_listing_performance

客服类工具：

- get_order_details
- get_shipping_status
- get_return_policy
- draft_support_response
- request_refund_approval
- issue_refund

可观测性工具：

- record_trace_event
- record_evaluation_result
- replay_workflow

### 9.3 Marketplace Adapter 接口

每个平台适配器都实现统一接口：

```text
MarketplaceAdapter
  validate_listing(payload) -> ValidationResult
  create_listing_draft(payload) -> ListingDraftResult
  publish_listing(payload, idempotency_key) -> PublishResult
  update_price(listing_id, price, idempotency_key) -> ActionResult
  update_inventory(listing_id, quantity, idempotency_key) -> ActionResult
  get_orders(filters) -> OrderList
  get_inventory(sku) -> InventorySnapshot
  get_performance(listing_id, date_range) -> PerformanceSnapshot
  issue_refund(order_id, amount, reason, idempotency_key) -> RefundResult
```

### 9.4 Mock Adapter 要求

Mock adapter 需要模拟：

- 平台字段规则。
- 类目必填属性。
- 平台费用模型。
- Listing 校验错误。
- 发布成功和失败。
- 限流或临时故障。
- 订单和运营数据。
- 退款策略限制。

这样 MVP 即使不接真实平台，也能体现真实工程复杂度。

### 9.5 未来真实平台接入要求

替换成真实 adapter 时，需要满足：

- 凭证存储在 secret manager，不进入 Agent 上下文。
- 使用 OAuth 或平台官方 token 流程。
- 不把原始凭证暴露给 LLM。
- 优先使用平台 sandbox。
- 所有真实写操作继续强制审批。
- 增加 reconciliation job，对比本地状态和平台状态。
- 支持 webhook 处理订单、库存、Listing 状态和退款事件。

## 10. 数据模型

### 10.1 核心实体

Tenant：

- 表示一个商家组织。
- 拥有用户、店铺、工作流、商品、供应商和审计日志。

User：

- 属于某个 tenant。
- 拥有角色和权限。

MarketplaceConnection：

- 表示一个平台账号或模拟渠道。
- 保存 adapter 类型、状态、地区和凭证引用。

Workflow：

- 表示一次 Agent 业务流程。
- 保存状态、目标、目标平台、当前步骤和最终结果。

WorkflowStep：

- 保存状态机中的每一步。
- 包含状态、输入摘要、输出摘要、时间戳和错误详情。

ToolCall：

- 保存工具名称、输入 hash、输出摘要、延迟、状态、错误、风险等级和 trace_id。

AgentTrace：

- 保存 Agent 消息、模型信息、prompt 版本、工具版本、token 用量、成本估算和父子 trace 关系。

ApprovalRequest：

- 保存请求动作、风险等级、payload、理由、审批人、决策和不可变审计引用。

ProductIdea：

- 保存商品想法、类目、目标市场和研究结果。

Supplier：

- 保存供应商属性、评分、风险说明和关联商品。

ListingDraft：

- 保存生成的 Listing 内容、平台、语言地区、版本、校验结果和审批状态。

PublishedListing：

- 保存模拟或真实 listing_id、平台、SKU、发布状态和最新同步状态。

Order：

- 保存模拟订单，用于客服和运营流程。

InventorySnapshot：

- 保存 SKU 级库存状态。

SupportTicket：

- 保存客户问题、关联订单、回复草稿、风险等级和处理状态。

EvaluationResult：

- 保存 Listing 质量、证据质量、风险合规、客服安全和流程成功率等评分。

AuditLog：

- 保存用户、Agent 和工具动作的不可变审计记录。

### 10.2 建议数据库表

- tenants
- users
- roles
- permissions
- marketplace_connections
- workflows
- workflow_steps
- agent_traces
- tool_calls
- approval_requests
- audit_logs
- product_ideas
- market_trend_records
- competitor_products
- review_records
- keyword_metrics
- suppliers
- profit_estimates
- listing_drafts
- listing_versions
- published_listings
- inventory_snapshots
- orders
- support_tickets
- evaluation_results
- prompt_versions
- tool_versions
- adapter_rules
- documents
- knowledge_chunks

### 10.3 数据隔离

所有核心业务表都应包含 tenant_id。Agent 工具必须接收 tenant_id，并在服务层强制校验访问权限。不能依赖 LLM 自己遵守租户边界。

## 11. 审批与风险策略

### 11.1 风险等级

低风险：

- 读取数据。
- 总结趋势。
- 生成草稿。
- 计算利润。
- 提出建议。

中风险：

- 创建 Listing 草稿。
- 生成客服回复草稿。
- 推荐价格。
- 推荐供应商。

高风险：

- 发布 Listing。
- 修改价格。
- 应用促销。
- 发送客服回复。
- 预留库存。

关键风险：

- 发起退款。
- 发放补偿。
- 下架商品。
- 推荐大额供应商订单。
- 未来接触真实凭证或真实平台写操作。

### 11.2 审批规则

- 低风险动作可以自动执行。
- 中风险动作可以执行，但必须记录并可见。
- 高风险动作执行前必须审批。
- 关键风险动作必须审批，并要求更强理由。
- 被拒绝动作必须停止或改走其他路径。

### 11.3 策略示例

- 如果贡献利润率低于 15%，阻止发布并要求人工审核。
- 如果 Listing 包含健康、安全、医疗或保证结果类声明，阻止发布。
- 如果退款金额超过配置阈值，必须审批。
- 如果客服工单情绪极端或包含法律威胁，必须升级。
- 如果供应商质量评分低于阈值，必须管理者审批。

## 12. 评估体系

### 12.1 评估维度

选品研究：

- 证据覆盖度。
- 竞品相关性。
- 评论痛点提取质量。
- 机会评分一致性。

利润分析：

- 计算正确性。
- 假设可见性。
- 敏感性分析完整度。

Listing 生成：

- 平台规则符合度。
- SEO 关键词使用。
- 声明安全性。
- 本地化质量。
- 必填字段完整度。

客服售后：

- 是否基于订单和政策数据。
- 语气质量。
- 退款安全性。
- 升级判断正确性。

工作流整体：

- 工具调用成功率。
- 人工审批正确性。
- 完成耗时。
- 单次 workflow 成本。
- 从模拟失败中恢复的能力。

### 12.2 评估实现

MVP 包含：

- 结构化字段的规则校验器。
- 确定性计算单元测试。
- 使用 LLM-as-judge 评估 Listing 质量和客服语气。
- 5-10 个黄金测试场景。
- Agent 工作流回归测试。
- 展示评估分数和理由的页面。

### 12.3 成功指标

MVP 成功标准：

- 用户可以完成完整的商品启动工作流。
- 至少使用三个 mock marketplace adapter。
- 高风险动作无法绕过审批。
- 主要 Agent 动作都有 trace。
- Listing 有校验分数和评估分数。
- 工具失败可以重试或清晰展示。
- 系统可以回放一次保存过的 workflow。

## 13. 可观测性与审计

### 13.1 Trace 要求

每次 workflow run 记录：

- workflow_id。
- trace_id。
- parent_trace_id。
- Agent 名称。
- 模型名称。
- prompt 版本。
- 工具版本。
- 输入摘要。
- 输出摘要。
- token 用量。
- 成本估算。
- 延迟。
- 工具调用。
- 错误。
- 审批状态。

### 13.2 可观测性页面

前端提供：

- 工作流时间线。
- Agent 步骤详情。
- 工具调用表。
- 审批历史。
- 评估结果。
- 成本和延迟汇总。
- 错误和重试历史。

### 13.3 审计日志规则

审计日志必须 append-only。敏感 payload 需要摘要化或脱敏。高风险动作必须保存足够信息，让审核者能理解发生了什么，同时不能暴露凭证或不必要的隐私数据。

## 14. 前端需求

### 14.1 主要页面

Dashboard：

- 活跃工作流。
- 待审批动作。
- 最近错误。
- 成本汇总。
- 平台健康状态。

Workflow Builder：

- 商品想法输入。
- 平台选择。
- 目标市场选择。
- 风险偏好。
- 可选供应商输入。

Workflow Detail：

- 状态机进度。
- Agent 输出。
- 证据链接。
- 工具调用。
- 评估分数。
- 重试控制。

Approval Center：

- 待审批高风险动作。
- Listing 发布或价格修改 diff。
- Agent 理由。
- 风险报告。
- 批准、拒绝、要求修改。

Listing Workspace：

- 多平台 Listing 草稿。
- 校验结果。
- 本地化视图。
- 版本历史。

Operations Monitor：

- 模拟运营指标。
- 库存。
- 评论。
- 优化建议。

Support Desk：

- 模拟客服工单。
- 订单详情。
- 回复草稿。
- 退款审批流程。

Observability：

- Trace。
- 工具调用。
- 评估结果。
- 成本和延迟。
- Workflow 回放。

### 14.2 交互原则

- 第一屏应该是可工作的运营 Dashboard，而不是营销首页。
- Agent 进度用结构化工作流展示，不用纯聊天记录展示。
- 审批动作必须明显、可理解。
- 证据和风险信号要靠近 Agent 建议。
- 失败状态要明确，并提供恢复方式。

## 15. 后端需求

### 15.1 推荐技术栈

- 后端 API：Python + FastAPI。
- Agent 编排：LangGraph 或 OpenAI Agents SDK。
- 数据库：PostgreSQL。
- 向量检索：pgvector 或 Qdrant。若复用现有 Agentic RAG 项目经验，MVP 可优先使用 Qdrant；若希望减少基础设施数量，可使用 pgvector。
- 队列：Celery、Dramatiq 或 RQ + Redis。
- 前端：React 或 Next.js。
- 可观测性：先自建 trace 表，后续可接 LangSmith 或 OpenTelemetry。
- 测试：pytest、Playwright、工作流回归 fixtures。

### 15.2 大模型与 RAG 模型配置

MVP 阶段暂时采用硅基流动 SiliconFlow，配置参考本地 Agentic RAG 项目中的模型配置，但新项目中不能硬编码 API key。

默认模型配置：

- LLM provider：siliconflow。
- LLM base_url：https://api.siliconflow.cn/v1。
- LLM model：deepseek-ai/DeepSeek-V3.2。
- LLM 调用接口：OpenAI-compatible `/chat/completions`。
- Embedding provider：siliconflow。
- Embedding model：BAAI/bge-m3。
- Embedding dimensions：1024。
- Reranker provider：siliconflow。
- Reranker model：BAAI/bge-reranker-v2-m3。
- Vision model：Qwen/Qwen3-VL-32B-Instruct，MVP 可先预留，用于后续商品图理解、Listing 图片审核和视觉素材 brief 检查。

推荐环境变量：

- SILICONFLOW_API_KEY。
- SILICONFLOW_BASE_URL。
- LLM_MODEL。
- EMBEDDING_MODEL。
- RERANKER_MODEL。
- VISION_MODEL。

配置要求：

- API key 只允许放在 `.env`、部署平台 secret 或 secret manager 中。
- PRD、README、代码仓库和 trace 日志中不能出现明文 API key。
- 模型名称、base_url、temperature、max_tokens、embedding dimensions、rerank top_n 统一放在模型配置文件中。
- Agent、RAG、评估器和工具层都从统一配置读取模型，避免不同模块散落硬编码。
- 测试环境默认使用 mock LLM、mock embedding 和 mock reranker，集成测试才允许调用真实 SiliconFlow。

建议默认参数：

- LLM temperature：普通运营解释可使用 0.7；结构化 JSON 输出、风险审核、工具规划建议使用 0.2-0.3。
- LLM max_tokens：MVP 默认 4096，长报告生成可单独提高。
- RAG initial_top_k：20。
- RAG rerank_top_k：5。
- RAG max_refinements：最多 3 次。
- RAG score_threshold：可从 0.3 起步，并在评估集上调参。

### 15.3 客服 Agent RAG 设计

客服 Agent 需要 RAG，但不应该把所有问题都交给 RAG。推荐采用“业务工具 + RAG 知识库 + 风险审核”的组合。

知识库集合建议：

- tenant_policy_docs：店铺级退换货、退款、保修、补偿政策。
- marketplace_policy_docs：平台级售后、禁售、评价回复和争议处理规则。
- product_docs：商品说明书、材质、安装、尺码、保养说明。
- faq_docs：常见问题和标准客服话术。
- logistics_docs：物流方式、时效、异常说明。

检索 metadata：

- tenant_id。
- marketplace。
- locale。
- document_type。
- product_id 或 sku。
- policy_version。
- effective_from。
- permission_scope。

推荐 RAG 流程：

1. Planner 判断是否需要 RAG：商品咨询、政策解释、退换货规则、保修说明需要 RAG；订单状态、物流轨迹、退款金额需要业务工具。
2. Retriever 使用 metadata filter 限定租户、平台、语言和商品范围。
3. 使用向量检索加 reranker 获取最相关证据。
4. Context assembler 去重并保留来源。
5. Evaluator 判断证据是否足以回答。
6. 如果证据不足，Agent 请求人工处理或要求补充知识，不允许编造。
7. Generator 生成带来源引用的客服回复草稿。
8. Risk & Review Agent 检查过度承诺、违规补偿、与政策冲突和情绪升级。

客服 RAG 验收标准：

- 普通商品咨询能引用商品说明或 FAQ。
- 退货、退款、保修问题能引用对应政策版本。
- 跨平台问题能按 marketplace 过滤，不混用平台规则。
- 跨租户数据严格隔离。
- 没有检索依据时回复进入人工处理。
- 所有检索结果、rerank 分数、来源和最终引用记录到 trace。

### 15.4 API 设计

建议 REST API：

- POST /workflows
- GET /workflows
- GET /workflows/{workflow_id}
- POST /workflows/{workflow_id}/cancel
- POST /workflows/{workflow_id}/retry
- GET /workflows/{workflow_id}/trace
- GET /workflows/{workflow_id}/evaluations
- GET /approvals
- POST /approvals/{approval_id}/approve
- POST /approvals/{approval_id}/reject
- GET /listings
- GET /listings/{listing_id}
- GET /support-tickets
- POST /support-tickets/{ticket_id}/draft-response
- GET /marketplaces
- GET /marketplaces/{marketplace_id}/rules

### 15.5 异步执行

长任务不能卡在一次 HTTP 请求里。

要求：

- API 创建 workflow 并入队。
- Worker 执行工作流图。
- UI 通过轮询或订阅查看进度。
- 每一步完成后持久化状态。
- 失败步骤可以尽量局部重试。

### 15.6 幂等性

写操作工具必须使用 idempotency_key：

- publish_listing
- update_price
- update_inventory
- issue_refund
- create_promotion

即使 MVP 是 mock 模式，也要实现幂等性，以体现生产化设计。

## 16. 安全与风控

### 16.1 权限控制

角色：

- Admin。
- Operator。
- Reviewer。
- Support。
- Read-only observer。

权限：

- workflow:create
- workflow:read
- workflow:cancel
- approval:review
- listing:publish
- price:update
- refund:issue
- support:respond
- observability:read

### 16.2 LLM 安全边界

- LLM 不接收密钥。
- LLM 不直接写外部系统。
- 工具层校验输入并执行权限控制。
- 工具输出涉及敏感信息时要摘要化。
- Agent 生成内容在执行前必须校验。

### 16.3 Prompt Injection 风险

潜在攻击面：

- 供应商描述。
- 竞品 Listing 文本。
- 评论内容。
- 客服消息。
- 上传文档。

缓解方式：

- 把外部文本当作不可信数据。
- 系统指令和检索内容分离。
- 使用 schema 化工具和权限控制。
- 执行前验证输出。
- 高风险动作必须审批。

## 17. 可扩展性设计

### 17.1 平台扩展

新增 marketplace 时，只需要实现 MarketplaceAdapter 并注册规则。

步骤：

1. 添加 adapter 元数据。
2. 添加 Listing schema 规则。
3. 添加费用模型。
4. 添加校验逻辑。
5. 添加 mock 数据生成器。
6. 后续添加真实 API client。
7. 添加 adapter 测试。

### 17.2 Agent 扩展

只有当一个职责有清晰输入、输出、工具和评估标准时，才新增 Agent。

未来可扩展 Agent：

- Advertising Agent：广告投放建议。
- Review Mining Agent：评论挖掘。
- Compliance Agent：合规审核。
- Demand Forecasting Agent：需求预测。
- Competitor Monitoring Agent：竞品监控。
- Supplier Negotiation Agent：供应商谈判辅助。
- Finance Reconciliation Agent：财务对账。

### 17.3 工作流扩展

第一条工作流是商品启动。未来可增加：

- Listing 优化工作流。
- 库存补货工作流。
- 差评恢复工作流。
- 价格调整工作流。
- 供应商比较工作流。
- 新市场扩张工作流。
- 客服升级工作流。

所有工作流复用工具注册中心、adapter 层、审批系统、trace 系统和评估体系。

### 17.4 数据扩展

MVP 要把 mock 数据生成器和业务逻辑分离。未来数据来源可以包括：

- 平台 API。
- CSV 上传。
- ERP 导出。
- 供应商表格。
- 合规允许范围内的网页数据采集。
- 第三方趋势 API。
- 客服系统。

## 18. MVP 开发里程碑

### 里程碑 1：基础设施

- 数据库 schema。
- Mock 数据 seed。
- 用户和租户模型。
- Marketplace adapter 接口。
- MockAmazon、MockShopify、MockTikTokShop。
- 带风险元数据的工具注册中心。

### 里程碑 2：Agent 工作流

- 商品启动工作流状态机。
- Supervisor Agent。
- Research、Profit、Supplier、Listing、Localization、Risk Agents。
- 异步 worker。
- 工作流持久化。

### 里程碑 3：审批与执行

- ApprovalRequest 模型。
- 审批中心页面。
- 模拟发布工具。
- 幂等性支持。
- 审计日志。

### 里程碑 4：运营监控与客服

- 模拟运营数据。
- Ops Agent。
- 客服工单。
- Customer Support Agent。
- 退款审批流程。

### 里程碑 5：可观测性与评估

- Trace 页面。
- 工具调用日志。
- 成本和延迟汇总。
- 评估结果。
- Workflow 回放。
- 黄金场景测试。

### 里程碑 6：作品集打磨

- Demo 脚本。
- 预置示例工作流。
- README 架构说明。
- 截图。
- 部署说明。
- 面试讲解要点。

## 19. MVP 验收标准

MVP 完成时应满足：

- 用户可以从 Dashboard 创建商品启动 workflow。
- 系统生成带证据的选品机会分析。
- 系统通过确定性工具计算利润。
- 系统评估至少两个供应商。
- 系统为至少三个 mock 平台生成 Listing。
- 系统校验不同平台的 Listing 规则。
- 系统在模拟发布前创建审批请求。
- 审批通过后 mock 发布 Listing，并生成平台 listing_id。
- 系统在发布后监控模拟表现。
- 客服 Agent 能为至少一个工单生成有依据的回复。
- 退款或补偿需要审批。
- Workflow detail 页面展示 trace、工具调用、审批和评估。
- 失败 adapter 调用可以重试。
- Demo 数据可以重置并回放。

## 20. 推荐 Demo 场景

推荐商品：可折叠床底收纳箱。

Demo 流程：

1. 创建任务：面向美国和英国市场，商品是“可折叠床底收纳箱”。
2. 选择 MockAmazon、MockShopify、MockTikTokShop。
3. Agent 发现需求信号和竞品痛点。
4. Profit 工具计算到岸成本和利润率。
5. Supplier Agent 推荐主供应商和备选供应商。
6. Listing Agent 生成三个平台的 Listing 草稿。
7. Risk Agent 标记一个无证据声明和一个低利润平台风险。
8. 用户接受修改建议。
9. 用户审批发布。
10. Mock adapter 发布 Listing。
11. Ops Agent 发现某个平台转化率较低。
12. Customer Support Agent 为物流延迟工单生成回复草稿。
13. Retrospective 总结本次铺货质量、风险和下一步动作。

这个场景具体、好理解，并且能展示全链路能力。

## 21. 工程风险

范围膨胀：

- 风险：Agent 和工作流太多，MVP 做不完。
- 缓解：先完成一条商品启动主工作流。

Agent 输出不可控：

- 风险：Demo 时输出波动过大。
- 缓解：使用 seeded mock data、结构化输出、校验器和工作流回放。

过度依赖 LLM：

- 风险：数学、规则和政策判断不可靠。
- 缓解：计算和规则检查放在确定性服务中。

项目看起来像聊天机器人：

- 风险：面试官认为只是 prompt wrapper。
- 缓解：突出状态机、工具层、adapter、审批、审计、评估和可观测性。

真实 API 接入拖慢进度：

- 风险：真实平台 API 需要账号、权限和审核。
- 缓解：先做 mock adapter，同时保留真实接入边界。

评估质量主观：

- 风险：很难判断 Agent 输出到底好不好。
- 缓解：结合规则校验、黄金场景和 LLM-as-judge。

## 22. 待确认问题

- Agent 编排框架优先选 LangGraph 还是 OpenAI Agents SDK？
- 前端优先用 Next.js 还是 React + Vite？
- MVP 是否实现真实认证，还是用 seed 用户和角色模拟？
- 第一版是否直接使用真实 LLM，还是先用 stubbed agents 打通工作流？
- seed 数据具体覆盖哪些商品类目？
- 部署优先考虑 Docker Compose、本地 VM，还是云服务？

推荐默认选择：

- 如果优先展示显式状态机和可控工作流，选择 LangGraph。
- 如果优先展示现代工具调用、guardrails、tracing，可以选择 OpenAI Agents SDK。
- 后端使用 FastAPI、PostgreSQL、Redis。
- 前端使用 Next.js 或 React。
- Agent 输出使用真实 LLM，但计算、校验和审批逻辑必须确定性实现。
- 使用 Docker Compose 保证作品集可复现。

## 23. 后续路线图

Phase 2：真实数据导入

- CSV 导入商品、供应商、订单、评论。
- 上传供应商报价表。
- 上传平台导出数据。
- 对政策文档和商品文档做向量检索。

Phase 3：真实平台连接器

- 优先接 Shopify，因为开发体验相对友好。
- 先支持真实商品草稿创建，再支持真实发布。
- 真实发布仍然强制审批。

Phase 4：高级跨境运营

- 多国家定价。
- 汇率换算。
- 税费和关税假设。
- 物流 SLA 模拟。
- 退货率预测。

Phase 5：增长与广告

- 关键词扩展。
- 广告活动草稿生成。
- 预算 guardrails。
- 短视频或图片 brief 生成。

Phase 6：团队和企业能力

- 多人审批。
- 角色化策略。
- 组织级审计导出。
- 定时监控任务。
- Webhook 和告警。

## 24. 面试讲解要点

可以重点讲：

- 为什么 Agent 应该通过工具执行动作，而不是直接访问外部 API。
- marketplace adapter 如何隔离平台差异。
- 为什么利润计算和规则检查要做成确定性服务。
- 人工审批如何降低真实业务风险。
- 可观测性如何让 Agent 行为可调试。
- 评估体系如何避免 prompt 或工具变更导致回归。
- 幂等性和重试为什么对外部写操作重要。
- mock adapter 如何让 MVP 快速开发，同时保留生产扩展边界。
- 如何从 MVP 演进到真实生产系统，而不是推倒重来。

## 25. 参考资料

- OpenAI Agents SDK：https://openai.github.io/openai-agents-python/
- LangGraph：https://docs.langchain.com/oss/python/langgraph/overview
- LangSmith：https://docs.smith.langchain.com/
- Amazon Selling Partner API：https://developer-docs.amazon.com/sp-api/
- Shopify Admin GraphQL API：https://shopify.dev/docs/api/admin-graphql/latest
- TikTok Shop API concepts：https://partner.tiktokshop.com/docv2/page/tts-api-concepts-overview
