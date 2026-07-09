# PRD: Cross-Border E-commerce Agent Platform

Version: 0.1  
Status: Draft for MVP development  
Date: 2026-07-09  
Primary goal: Build a production-minded portfolio project for Agent Engineer roles

## 1. Executive Summary

This project is a full-cycle cross-border e-commerce agent platform for small and medium sellers. The MVP uses a multi-marketplace simulation layer instead of direct production API integrations, while preserving the same engineering boundaries needed for future Amazon, Shopify, TikTok Shop, WooCommerce, or other marketplace connectors.

The platform helps sellers move from product opportunity discovery to listing creation, approval, mock publishing, operations monitoring, customer support, and retrospective optimization. It is designed to demonstrate real agent engineering capability: multi-step orchestration, tool calling, marketplace adapters, human approval, risk controls, observability, evaluation, async execution, audit logging, and extensible system boundaries.

The MVP should not look like a chatbot demo. It should behave like a small production system where agents operate through controlled tools, risky actions require approval, every decision is traceable, and each workflow can be replayed and evaluated.

## 2. Product Positioning

### 2.1 Product Name

Working name: Cross-Border CommerceOps Agent

### 2.2 One-Sentence Pitch

An agentic operations platform that helps cross-border sellers discover product opportunities, calculate profitability, generate localized marketplace listings, publish through controlled adapters, monitor early performance, and handle customer issues with human approval and full auditability.

### 2.3 Target Users

- Cross-border e-commerce sellers operating across multiple marketplaces.
- Small merchant teams that lack dedicated product research, listing, operations, and support specialists.
- Internal operators who need repeatable workflows instead of one-off AI chat.

### 2.4 Portfolio Objective

For job interviews, the project should demonstrate:

- Agent workflow design rather than single-prompt generation.
- Tool registry and marketplace adapter abstraction.
- Multi-agent collaboration with bounded responsibilities.
- Human-in-the-loop approval for risky business actions.
- Evaluation and guardrails for generated outputs.
- Observability across agent reasoning, tool calls, latency, cost, and failures.
- Engineering awareness of production constraints: retries, idempotency, permissions, data isolation, audit logs, and versioning.

## 3. Problem Statement

Cross-border sellers often need to coordinate product research, supplier comparison, profitability analysis, localized listing creation, marketplace-specific publishing, inventory monitoring, and customer support. These workflows are repetitive but risky. Bad automation can publish misleading listings, misprice products, trigger compliance issues, refund the wrong order, or make decisions without evidence.

General AI chat tools can generate copy or suggestions, but they do not provide:

- Marketplace-specific execution boundaries.
- Traceable decisions and evidence chains.
- Approval workflows for sensitive actions.
- Tool permissions and risk classification.
- Repeatable workflows that can be monitored and replayed.
- Evaluation metrics that separate useful agent behavior from plausible text.

This platform addresses that gap by treating the AI as an agent inside a controlled operations system.

## 4. Goals and Non-Goals

### 4.1 MVP Goals

- Provide one complete workflow from product opportunity discovery to mock marketplace publishing and operations follow-up.
- Support multiple simulated marketplace adapters with different rules and field constraints.
- Allow agents to call tools for research, profitability calculation, supplier scoring, listing generation, listing validation, publishing, order lookup, support response drafting, and monitoring.
- Require human approval for high-risk actions such as publishing listings, changing prices, issuing refunds, or removing products.
- Record traces, tool calls, decisions, approvals, evaluation scores, and audit logs.
- Provide a UI for launching workflows, inspecting agent progress, approving actions, reviewing generated listings, and viewing observability data.
- Use architecture that can later replace mock adapters with real Amazon, Shopify, TikTok Shop, or WooCommerce connectors.

### 4.2 MVP Non-Goals

- Directly connect to real seller accounts in the first version.
- Automate real money movement, real refunds, or real listing publication.
- Implement a full ERP, WMS, CRM, or ad management system.
- Build a perfect demand forecasting model.
- Support every country, language, category, and marketplace rule.
- Replace human business judgment for final launch decisions.

### 4.3 Future Goals

- Add real marketplace integrations.
- Add real web trend collection and competitor monitoring.
- Add supplier data ingestion from spreadsheets or external APIs.
- Add multi-tenant billing and role-based team collaboration.
- Add richer evaluation datasets and regression tests for agent behavior.
- Add event-driven monitoring for orders, inventory, reviews, ads, and support tickets.

## 5. MVP Scope

### 5.1 Primary MVP Workflow

The first workflow is:

1. Seller creates a product exploration task.
2. Product Research Agent analyzes mock market trends, competitor products, review pain points, and price bands.
3. Profit Analyst Agent estimates landed cost, platform fees, ad cost, return risk, gross margin, and break-even price.
4. Supplier Agent compares candidate suppliers by price, MOQ, lead time, quality risk, and fulfillment reliability.
5. Listing Agent drafts marketplace-specific listings for Amazon-like, Shopify-like, and TikTok Shop-like channels.
6. Localization Agent adapts titles, descriptions, sizing, units, claims, and cultural language for target markets.
7. Risk & Review Agent checks profitability, listing quality, unsupported claims, missing evidence, and marketplace rule violations.
8. Human reviewer approves or rejects listing publication.
9. Marketplace Adapter mock-publishes approved listings.
10. Ops Agent monitors simulated early performance: views, conversion, orders, inventory, reviews, and return signals.
11. Customer Support Agent drafts responses for simulated customer tickets.
12. System generates a retrospective with what worked, what failed, and recommended next actions.

### 5.2 Supported Mock Marketplaces

The MVP includes three simulated marketplace adapters:

- MockAmazonAdapter: strict catalog attributes, title length limits, bullet points, category-specific required fields, fee model, FBA-like logistics assumptions.
- MockShopifyAdapter: independent-store product page, SEO fields, inventory locations, flexible content, simpler publication flow.
- MockTikTokShopAdapter: shorter commerce content, creator-friendly hooks, video-oriented selling points, tighter policy checks for claims.

These adapters should implement the same interface but enforce different validation rules.

### 5.3 Example Product Categories

The MVP should start with 2-3 categories to keep rules manageable:

- Home organization products.
- Pet accessories.
- Fitness or wellness accessories.

Avoid categories with heavy compliance needs in MVP, such as food, supplements, medical devices, children's safety products, cosmetics, batteries, or regulated electronics.

## 6. Personas and Use Cases

### 6.1 Merchant Operator

The operator wants to quickly decide whether a product idea is worth launching. They care about margin, demand, supplier risk, and listing quality.

Core actions:

- Start product research task.
- Review opportunity score and profit estimate.
- Compare suppliers.
- Approve or reject generated listings.
- Monitor launch performance.

### 6.2 E-commerce Operations Manager

The manager wants visibility and control. They care about process quality, approvals, errors, and audit trails.

Core actions:

- View active workflows.
- Inspect agent decisions and tool calls.
- Approve risky actions.
- Review failed tasks and retry.
- Compare evaluation scores across runs.

### 6.3 Customer Support Specialist

The support specialist wants draft replies grounded in order and policy data, but does not want the agent issuing refunds without approval.

Core actions:

- Open support ticket.
- Let agent inspect order and logistics data.
- Review response draft.
- Approve compensation or refund when required.

### 6.4 Technical Reviewer or Interviewer

The interviewer wants to understand whether this is a real agent system or a wrapper around a model call.

Expected evidence:

- Clear workflow graph.
- Typed tool interfaces.
- Marketplace adapter abstraction.
- Human approval and audit logs.
- Observability view.
- Evaluation harness.
- Failure handling and replay.

## 7. Product Requirements

### 7.1 Workflow Launch

Users can create a new cross-border launch task with:

- Product idea or seed keyword.
- Target marketplaces.
- Target countries or locales.
- Product category.
- Target price range.
- Optional supplier candidates.
- Risk preference: conservative, balanced, aggressive.

Acceptance criteria:

- Task is persisted with a unique workflow ID.
- Task enters a visible state machine.
- The user can inspect progress step by step.
- The workflow can be resumed after interruption.

### 7.2 Product Opportunity Research

The system should analyze mock trend data, competitor listings, price distribution, and review pain points.

MVP inputs:

- Mock trend records.
- Mock competitor product records.
- Mock review snippets.
- Mock search keyword records.

Outputs:

- Opportunity score.
- Demand rationale.
- Price band analysis.
- Competitor summary.
- Review pain points.
- Recommended positioning.
- Evidence references.

Acceptance criteria:

- Every recommendation links to mock evidence records.
- The agent distinguishes facts from assumptions.
- Missing data is explicitly reported.

### 7.3 Profitability Analysis

The system calculates estimated profitability.

Inputs:

- Supplier unit cost.
- MOQ.
- Shipping cost.
- Customs and duties assumption.
- Marketplace commission.
- Payment fee.
- Fulfillment fee.
- Ad cost assumption.
- Return rate assumption.

Outputs:

- Landed cost.
- Gross margin.
- Contribution margin.
- Break-even selling price.
- Sensitivity analysis for ad cost and return rate.
- Profit risk score.

Acceptance criteria:

- Calculations are deterministic service calls, not purely LLM-generated math.
- Agent can explain the result in business language.
- Assumptions are stored and visible.

### 7.4 Supplier Evaluation

The system scores supplier candidates.

Inputs:

- Unit price.
- MOQ.
- Lead time.
- Quality score.
- Defect history.
- Response time.
- Region.
- Certifications or missing certifications.

Outputs:

- Supplier ranking.
- Risk notes.
- Recommended supplier.
- Backup supplier.
- Questions to ask supplier before purchase.

Acceptance criteria:

- Supplier score is computed by a transparent scoring function.
- LLM may summarize and reason, but the numeric formula is inspectable.
- High-risk suppliers are flagged.

### 7.5 Listing Generation

The system generates platform-specific listing drafts.

Outputs per marketplace:

- Title.
- Short description.
- Bullet points or feature list.
- Long description.
- SEO keywords.
- Product attributes.
- Variant structure.
- Image brief.
- Compliance notes.
- Localization notes.

Acceptance criteria:

- Listing drafts comply with adapter field constraints.
- Unsupported claims are flagged or removed.
- The agent generates different listing shapes for different marketplaces.
- The listing version is stored before approval.

### 7.6 Localization

The system adapts listings for target markets.

MVP localization features:

- Language adaptation.
- Units and sizing.
- Tone adjustment.
- Country-specific wording.
- Claims and disclaimer review.

Acceptance criteria:

- Localized content is linked to the source listing version.
- Localization changes are visible in a diff-like review panel.
- Risky claims are highlighted before approval.

### 7.7 Risk Review and Guardrails

The system reviews outputs before execution.

Risk checks:

- Profit margin below threshold.
- High return-rate assumption.
- Unsupported claims.
- Missing required marketplace attributes.
- Overly aggressive discounting.
- Supplier quality risk.
- Restricted category warning.
- Potential trademark or IP concern.
- Refund or compensation above policy threshold.

Acceptance criteria:

- Each workflow has a risk report.
- High-risk findings block auto-execution.
- The user sees the reason for approval requirement.

### 7.8 Human Approval

Certain operations require explicit approval.

Approval-required actions:

- Publish listing.
- Update price.
- Apply promotion or coupon.
- Issue refund.
- Send compensation.
- Delist product.
- Change inventory reservation.

Approval record must include:

- Requested action.
- Actor requesting action.
- Tool and adapter involved.
- Input payload.
- Risk level.
- Agent rationale.
- Reviewer decision.
- Timestamp.

Acceptance criteria:

- No high-risk action executes without approval.
- Rejected actions are recorded with reason.
- Approved actions become immutable audit events.

### 7.9 Mock Publishing

The system publishes approved listings through mock adapters.

Behavior:

- Validate listing payload.
- Return mock platform listing ID.
- Record publication status.
- Simulate platform-specific errors.

Acceptance criteria:

- Same listing request can be safely retried using idempotency key.
- Validation errors are visible to the agent and user.
- The system can recover from transient mock failures.

### 7.10 Operations Monitoring

The system monitors simulated performance after mock publishing.

Metrics:

- Impressions.
- Clicks.
- Conversion rate.
- Orders.
- Revenue.
- Inventory.
- Review rating.
- Return signals.
- Support ticket volume.

Outputs:

- Performance summary.
- Anomaly detection.
- Suggested next actions.
- Price or listing optimization proposals.

Acceptance criteria:

- Recommendations reference observed metrics.
- Risky optimization actions require approval.
- Monitoring results are tied to listing versions.

### 7.11 Customer Support

The system drafts support responses based on order, logistics, product, and policy data.

Ticket types:

- Where is my order?
- Product does not match expectation.
- Return request.
- Refund request.
- Negative review response.

Acceptance criteria:

- Support answers cite order and policy data.
- Refund and compensation actions require approval.
- The agent cannot invent shipping status.
- The user can edit before sending.

### 7.12 Retrospective

At the end of a workflow, the platform generates a retrospective.

Contents:

- Summary of product opportunity.
- Final decision and reasoning.
- Published listing IDs.
- Key risks.
- Performance after launch.
- What to improve.
- Suggested next experiment.

Acceptance criteria:

- Retrospective is generated from stored workflow state, not a fresh hallucinated summary.
- It includes links to trace, evidence, approvals, and evaluation results.

## 8. Agent System Design

### 8.1 Agent Roles

Product Research Agent:

- Finds opportunity signals.
- Summarizes demand, competitor gaps, and review pain points.
- Must attach evidence IDs.

Profit Analyst Agent:

- Calls deterministic calculation tools.
- Explains profitability and risk.
- Does not perform hidden arithmetic in prose.

Supplier Agent:

- Scores suppliers.
- Flags supply chain risks.
- Suggests backup suppliers.

Listing Agent:

- Drafts platform-specific listing content.
- Uses marketplace rules and product facts.
- Avoids unsupported claims.

Localization Agent:

- Adapts listing content for target locale.
- Checks cultural and unit differences.

Ops Agent:

- Monitors metrics and detects anomalies.
- Proposes operational actions.

Customer Support Agent:

- Drafts support responses.
- Uses order and policy tools.
- Escalates risky cases.

Risk & Review Agent:

- Evaluates outputs and requested actions.
- Assigns risk level.
- Blocks unsafe execution.

Supervisor Agent:

- Owns workflow state.
- Chooses next step.
- Delegates to specialized agents.
- Requests approval when needed.

### 8.2 Agent Boundary Rules

- Agents do not directly access database tables.
- Agents operate through typed tools.
- Tools enforce permissions, validation, idempotency, and audit logging.
- Deterministic calculations stay outside the LLM.
- High-risk actions must pass through approval.
- Every tool call includes tenant ID, workflow ID, actor ID, trace ID, and idempotency key where relevant.

### 8.3 Workflow State Machine

Recommended states:

- draft
- queued
- researching
- analyzing_profit
- evaluating_suppliers
- drafting_listings
- localizing
- reviewing_risk
- awaiting_approval
- executing
- monitoring
- handling_support
- retrospective
- completed
- failed
- cancelled

Each transition should be explicit and persisted.

### 8.4 Failure Handling

Failure types:

- Tool validation error.
- Marketplace adapter error.
- LLM output schema error.
- Missing evidence.
- Calculation input missing.
- Approval rejected.
- Queue timeout.
- Rate limit or transient provider error.

Recovery patterns:

- Retry with backoff for transient errors.
- Ask agent to repair structured output for schema errors.
- Pause for user input when required data is missing.
- Mark blocked when approval is rejected.
- Preserve partial outputs and trace history.

## 9. Tool and Adapter Architecture

### 9.1 Tool Registry

The platform should expose tools through a registry.

Each tool definition includes:

- Name.
- Description.
- Input schema.
- Output schema.
- Risk level.
- Required permission.
- Idempotency requirement.
- Timeout.
- Retry policy.
- Audit logging policy.
- Whether human approval is required.

### 9.2 Core Tool Categories

Research tools:

- search_market_trends
- get_competitor_products
- get_review_pain_points
- get_keyword_metrics

Profit tools:

- estimate_landed_cost
- calculate_marketplace_fees
- calculate_break_even_price
- run_margin_sensitivity

Supplier tools:

- list_supplier_candidates
- score_supplier
- compare_suppliers

Listing tools:

- create_listing_draft
- validate_listing
- localize_listing
- generate_image_brief

Marketplace tools:

- publish_listing
- update_price
- update_inventory
- get_orders
- get_listing_performance

Support tools:

- get_order_details
- get_shipping_status
- get_return_policy
- draft_support_response
- request_refund_approval
- issue_refund

Observability tools:

- record_trace_event
- record_evaluation_result
- replay_workflow

### 9.3 Marketplace Adapter Interface

Adapters should implement a shared contract:

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

### 9.4 Mock Adapter Requirements

Mock adapters must simulate:

- Marketplace-specific field rules.
- Category required attributes.
- Fee models.
- Listing validation errors.
- Publication success and failure.
- Rate limits or transient failures.
- Order and performance data.
- Refund policy constraints.

This makes the MVP believable without real account dependencies.

### 9.5 Future Real Adapter Requirements

When replacing mock adapters with real connectors:

- Store credentials in a secret manager, not in agent context.
- Use OAuth or platform-specific token flow where available.
- Never expose raw credentials to LLM prompts.
- Add platform sandbox support where possible.
- Keep write actions behind approval.
- Implement reconciliation jobs to compare local state with platform state.
- Handle platform webhooks for orders, inventory, listing status, and refunds.

## 10. Data Model

### 10.1 Core Entities

Tenant:

- Represents a seller organization.
- Owns users, shops, workflows, products, suppliers, and audit logs.

User:

- Belongs to tenant.
- Has role and permissions.

MarketplaceConnection:

- Represents a marketplace account or mock channel.
- Stores adapter type, status, region, and credential reference.

Workflow:

- Represents one agentic business process.
- Stores state, objective, target marketplaces, current step, and final outcome.

WorkflowStep:

- Stores each step in the state machine.
- Includes status, input summary, output summary, timestamps, and error details.

ToolCall:

- Stores tool name, input hash, output summary, latency, status, error, risk level, and trace ID.

AgentTrace:

- Stores agent messages, model metadata, prompt version, tool version, token usage, cost estimate, and parent-child relationship.

ApprovalRequest:

- Stores requested action, risk level, payload, rationale, reviewer, decision, and immutable audit reference.

ProductIdea:

- Stores seed product idea, category, target locale, and research output.

Supplier:

- Stores supplier attributes, score, risk notes, and product relationships.

ListingDraft:

- Stores generated listing content, marketplace, locale, version, validation result, and approval state.

PublishedListing:

- Stores mock or real listing ID, marketplace, SKU, publication status, and latest synced state.

Order:

- Stores mock order records for support and operations workflows.

InventorySnapshot:

- Stores SKU-level inventory state.

SupportTicket:

- Stores customer issue, linked order, draft response, risk level, and resolution state.

EvaluationResult:

- Stores scores for listing quality, evidence quality, risk compliance, support safety, and workflow success.

AuditLog:

- Immutable record of user, agent, and tool actions.

### 10.2 Suggested Database Tables

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

### 10.3 Data Isolation

Every business table should include tenant_id. Agent tools must require tenant_id and enforce access at the service layer. The LLM should never be trusted to enforce tenant boundaries.

## 11. Approval and Risk Policy

### 11.1 Risk Levels

Low risk:

- Read data.
- Summarize trends.
- Draft content.
- Calculate profit.
- Suggest next actions.

Medium risk:

- Create listing draft.
- Generate customer reply draft.
- Recommend pricing.
- Recommend supplier.

High risk:

- Publish listing.
- Update price.
- Apply promotion.
- Send customer response.
- Reserve inventory.

Critical risk:

- Issue refund.
- Send compensation.
- Delist product.
- Change supplier order recommendation above threshold.
- Touch real credentials or real platform writes in future versions.

### 11.2 Approval Rules

- Low-risk actions can execute automatically.
- Medium-risk actions can execute but must be logged and visible.
- High-risk actions require approval before execution.
- Critical-risk actions require approval and stronger justification.
- Rejected actions must stop or reroute the workflow.

### 11.3 Policy Examples

- If estimated contribution margin is below 15%, block publish until reviewed.
- If listing contains health, safety, medical, or guaranteed-result claims, block publish.
- If refund amount exceeds configured threshold, require approval.
- If support ticket sentiment is angry or legal-threatening, escalate.
- If supplier quality score is below threshold, require manager approval.

## 12. Evaluation Strategy

### 12.1 Evaluation Dimensions

Product research:

- Evidence coverage.
- Competitor relevance.
- Pain point extraction quality.
- Opportunity score consistency.

Profit analysis:

- Calculation correctness.
- Assumption visibility.
- Sensitivity analysis coverage.

Listing generation:

- Marketplace rule compliance.
- SEO keyword usage.
- Claim safety.
- Localization quality.
- Completeness of required fields.

Support:

- Groundedness in order and policy data.
- Tone quality.
- Refund safety.
- Escalation correctness.

Workflow:

- Tool success rate.
- Human approval correctness.
- Time to completion.
- Cost per workflow.
- Recovery from simulated failures.

### 12.2 Evaluation Implementation

MVP should include:

- Rule-based validators for structured fields.
- Deterministic calculation tests.
- LLM-as-judge evaluation for listing quality and support tone.
- Golden test cases for 5-10 product launch scenarios.
- Regression tests for agent workflows.
- Manual review page showing evaluation scores and rationales.

### 12.3 Success Metrics

MVP success is achieved when:

- A user can complete the full product launch workflow in demo mode.
- At least three mock marketplace adapters are used.
- High-risk actions cannot bypass approval.
- All major agent actions are traceable.
- Listings receive validation and evaluation scores.
- A failed tool call can be retried or surfaced clearly.
- The system can replay a saved workflow for demo and debugging.

## 13. Observability and Auditability

### 13.1 Trace Requirements

Each workflow run should capture:

- workflow_id
- trace_id
- parent_trace_id
- agent name
- model name
- prompt version
- tool version
- input summary
- output summary
- token usage
- cost estimate
- latency
- tool calls
- errors
- approval state

### 13.2 Observability UI

The UI should provide:

- Workflow timeline.
- Agent step details.
- Tool call table.
- Approval history.
- Evaluation results.
- Cost and latency summary.
- Error and retry history.

### 13.3 Audit Log Rules

Audit logs should be append-only. Sensitive payloads should be summarized or redacted where appropriate. High-risk actions should store enough detail for a reviewer to understand what happened without exposing credentials or unnecessary private data.

## 14. Frontend Requirements

### 14.1 Main Views

Dashboard:

- Active workflows.
- Pending approvals.
- Recent errors.
- Cost summary.
- Marketplace health.

Workflow Builder:

- Product idea input.
- Marketplace selection.
- Target locale.
- Risk preference.
- Optional supplier input.

Workflow Detail:

- State machine progress.
- Agent outputs.
- Evidence links.
- Tool calls.
- Evaluation scores.
- Retry controls.

Approval Center:

- Pending risky actions.
- Diff view for listing publication or price change.
- Agent rationale.
- Risk report.
- Approve, reject, request changes.

Listing Workspace:

- Marketplace-specific listing drafts.
- Validation results.
- Localization view.
- Version history.

Operations Monitor:

- Mock performance metrics.
- Inventory.
- Reviews.
- Suggested optimizations.

Support Desk:

- Mock tickets.
- Order details.
- Draft responses.
- Refund approval flow.

Observability:

- Traces.
- Tool calls.
- Evaluation results.
- Cost and latency.
- Replay workflow.

### 14.2 UX Principles

- The first screen should be the working dashboard, not a marketing landing page.
- Show agent progress as a structured workflow, not an opaque chat transcript.
- Make approvals prominent and understandable.
- Show evidence and risk signals close to generated recommendations.
- Make failure states explicit and recoverable.

## 15. Backend Requirements

### 15.1 Suggested Stack

- Backend API: Python + FastAPI.
- Agent orchestration: LangGraph or OpenAI Agents SDK.
- Database: PostgreSQL.
- Vector search: pgvector.
- Queue: Celery, Dramatiq, or RQ with Redis.
- Frontend: React or Next.js.
- Observability: custom trace tables first; optional LangSmith or OpenTelemetry later.
- Testing: pytest for backend, Playwright for frontend, workflow regression fixtures.

### 15.2 API Surface

Suggested REST endpoints:

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

### 15.3 Async Execution

Long-running workflows should run outside the request-response cycle.

Requirements:

- API creates workflow and enqueues job.
- Worker executes workflow graph.
- UI polls or subscribes to progress.
- State is persisted after every step.
- Failed steps can be retried without rerunning the whole workflow where possible.

### 15.4 Idempotency

Write-like tool calls should use idempotency keys:

- publish_listing
- update_price
- update_inventory
- issue_refund
- create_promotion

Idempotency is important even in mock mode because it demonstrates production readiness.

## 16. Security and Safety Requirements

### 16.1 Access Control

Roles:

- Admin.
- Operator.
- Reviewer.
- Support.
- Read-only observer.

Permissions:

- workflow:create
- workflow:read
- workflow:cancel
- approval:review
- listing:publish
- price:update
- refund:issue
- support:respond
- observability:read

### 16.2 LLM Safety Boundary

- The LLM never receives secrets.
- The LLM never directly writes to external systems.
- Tools validate input and enforce permissions.
- Tool outputs are summarized when sensitive.
- Agent-generated content is checked before execution.

### 16.3 Prompt Injection Considerations

Potential attack surfaces:

- Supplier descriptions.
- Competitor listing text.
- Review content.
- Customer support messages.
- Uploaded documents.

Mitigations:

- Treat external text as untrusted data.
- Keep system instructions separate from retrieved content.
- Use tools with schemas and permissions.
- Validate outputs before execution.
- Require approval for high-risk actions.

## 17. Extensibility Plan

### 17.1 Marketplace Extensibility

New marketplaces should be added by implementing MarketplaceAdapter and registering rules.

Extension steps:

1. Add adapter metadata.
2. Add listing schema rules.
3. Add fee model.
4. Add validation logic.
5. Add mock data generator.
6. Add real API client later.
7. Add adapter-specific tests.

### 17.2 Agent Extensibility

New agents should be added when a responsibility has clear inputs, outputs, tools, and evaluation criteria.

Potential future agents:

- Advertising Agent.
- Review Mining Agent.
- Compliance Agent.
- Demand Forecasting Agent.
- Competitor Monitoring Agent.
- Supplier Negotiation Agent.
- Finance Reconciliation Agent.

### 17.3 Workflow Extensibility

The first workflow is product launch. Future workflows:

- Listing optimization.
- Inventory replenishment.
- Negative review recovery.
- Price adjustment.
- Supplier comparison.
- New market expansion.
- Customer support escalation.

Each workflow should reuse the same tool registry, adapter layer, approval system, trace system, and evaluation framework.

### 17.4 Data Extensibility

The MVP should keep mock data generators separate from application logic. Later, data can come from:

- Marketplace APIs.
- CSV uploads.
- ERP exports.
- Supplier spreadsheets.
- Web scraping where legal and permitted.
- Third-party trend APIs.
- Customer support platforms.

## 18. MVP Milestones

### Milestone 1: Foundation

- Database schema.
- Mock data seed.
- User and tenant model.
- Marketplace adapter interface.
- MockAmazon, MockShopify, MockTikTokShop adapters.
- Tool registry with risk metadata.

### Milestone 2: Agent Workflow

- Product launch workflow state machine.
- Supervisor Agent.
- Research, Profit, Supplier, Listing, Localization, Risk agents.
- Async worker execution.
- Workflow persistence.

### Milestone 3: Approval and Execution

- Approval request model.
- Approval center UI.
- Publish listing mock tool.
- Idempotency support.
- Audit logs.

### Milestone 4: Monitoring and Support

- Mock performance data.
- Ops Agent.
- Support tickets.
- Customer Support Agent.
- Refund approval flow.

### Milestone 5: Observability and Evaluation

- Trace view.
- Tool call logs.
- Cost and latency summary.
- Evaluation results.
- Workflow replay.
- Golden scenario tests.

### Milestone 6: Polish for Portfolio

- Demo script.
- Seeded example workflows.
- README architecture section.
- Screenshots.
- Deployment instructions.
- Interview talking points.

## 19. Acceptance Criteria for MVP

The MVP is complete when:

- A user can start a product launch workflow from the dashboard.
- The system produces product opportunity analysis with evidence.
- The system calculates profit using deterministic tools.
- The system evaluates at least two suppliers.
- The system generates listings for at least three mock marketplaces.
- The system validates marketplace-specific listing rules.
- The system creates an approval request before mock publishing.
- Approved listings are mock-published and assigned platform listing IDs.
- The system monitors simulated performance after publishing.
- The support agent drafts a grounded response for at least one ticket.
- Refund or compensation requires approval.
- The workflow detail page shows traces, tool calls, approvals, and evaluations.
- Failed adapter calls can be retried.
- Demo data can be reset and replayed.

## 20. Demo Scenario

Recommended demo product: foldable under-bed storage organizer.

Demo flow:

1. Start a workflow for "foldable under-bed storage organizer" targeting US and UK.
2. Select MockAmazon, MockShopify, and MockTikTokShop.
3. Agent identifies demand signals and competitor pain points.
4. Profit tool calculates landed cost and margin.
5. Supplier Agent recommends one supplier and one backup.
6. Listing Agent generates three marketplace-specific drafts.
7. Risk Agent flags one unsupported claim and one low-margin marketplace.
8. User edits or accepts suggested revision.
9. User approves publishing.
10. Mock adapters publish listings.
11. Ops Agent detects low conversion on one channel.
12. Customer Support Agent drafts a response for a shipping delay ticket.
13. Retrospective summarizes launch quality, risk, and next actions.

This scenario is concrete, easy to understand, and broad enough to show the full platform.

## 21. Engineering Risks

Scope creep:

- Risk: Too many agents and workflows make the MVP unfinished.
- Mitigation: Build one full product launch workflow first.

Agent unpredictability:

- Risk: Outputs vary too much for demos.
- Mitigation: Use seeded mock data, structured outputs, validation, and replay.

Over-reliance on LLM:

- Risk: Math and policy decisions become unreliable.
- Mitigation: Keep calculations and rule checks deterministic.

Weak production story:

- Risk: Project looks like a chatbot.
- Mitigation: Prioritize state machine, adapters, approval, audit, evaluation, and observability.

API integration delays:

- Risk: Real marketplace APIs require credentials and review.
- Mitigation: Use mock adapters first and preserve connector architecture.

Evaluation quality:

- Risk: Agent quality is subjective.
- Mitigation: Combine rule-based validators, golden scenarios, and LLM-as-judge scores.

## 22. Open Questions

- Which orchestration framework should be selected first: LangGraph or OpenAI Agents SDK?
- Should the first frontend be built with Next.js or plain React + Vite?
- Should authentication be implemented in MVP or simulated with seeded roles?
- Should the project include real LLM calls from day one or start with stubbed agents for workflow development?
- Which exact categories should be included in seed data?
- Which deployment target should be optimized first: local Docker Compose, cloud VM, or serverless?

Recommended default answers:

- Use LangGraph if the priority is explicit stateful workflow control.
- Use OpenAI Agents SDK if the priority is showcasing modern tool calling, guardrails, and tracing with a simpler Python-first agent framework.
- Use FastAPI, PostgreSQL, Redis, and React or Next.js.
- Start with real LLM calls for agent outputs, but keep deterministic tools and seeded data.
- Use Docker Compose for portfolio reproducibility.

## 23. Future Roadmap

Phase 2: Real Data Ingestion

- CSV import for products, suppliers, orders, and reviews.
- Uploaded supplier sheets.
- Uploaded marketplace exports.
- Vector search over policies and product documents.

Phase 3: Real Marketplace Connector

- Start with Shopify because developer experience is relatively straightforward.
- Add real product draft creation before real publishing.
- Keep publish approval mandatory.

Phase 4: Advanced Cross-Border Operations

- Multi-country pricing.
- Currency conversion.
- Tax and duty assumptions.
- Shipping SLA simulation.
- Return-rate forecasting.

Phase 5: Growth and Ads

- Keyword expansion.
- Ad campaign draft generation.
- Budget guardrails.
- Creative brief generation.

Phase 6: Team and Enterprise Features

- Multi-user approvals.
- Role-based policies.
- Organization-level audit export.
- Scheduled monitoring jobs.
- Webhooks and alerting.

## 24. Interview Talking Points

Use this project to explain:

- Why agents should operate through tools rather than direct API access.
- How marketplace adapters isolate platform-specific rules.
- Why deterministic services should handle calculations.
- How human approval reduces risk for write operations.
- How observability makes agent behavior debuggable.
- How evaluation prevents regressions in prompt and tool changes.
- How idempotency and retries matter for real external actions.
- How mock adapters make development fast while preserving real integration boundaries.
- How to evolve from MVP to production without rewriting the architecture.

## 25. References

- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/
- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangSmith documentation: https://docs.smith.langchain.com/
- Amazon Selling Partner API: https://developer-docs.amazon.com/sp-api/
- Shopify Admin GraphQL API: https://shopify.dev/docs/api/admin-graphql/latest
- TikTok Shop API concepts: https://partner.tiktokshop.com/docv2/page/tts-api-concepts-overview

