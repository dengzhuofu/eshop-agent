# 节点 04：确定性业务服务

时间：2026-07-09  
提交：`15e4a2b`  
状态：已完成

## 本节点目标

- 将利润测算、供应商评分和风险分类从 LLM 中剥离出来，做成可测试的确定性服务。
- 为后续 Agent 工具调用提供稳定、可解释、可回归测试的业务能力。

## 已完成内容

- 新增 `backend/app/services/profit.py`：
  - `ProfitInput`
  - `ProfitEstimate`
  - `estimate_profit`
- 新增 `backend/app/services/suppliers.py`：
  - `SupplierInput`
  - `SupplierScore`
  - `score_supplier`
- 新增 `backend/app/services/risk.py`：
  - `RiskAssessment`
  - `classify_listing_risk`
- 新增测试：
  - `backend/tests/test_profit.py`
  - `backend/tests/test_suppliers.py`
  - `backend/tests/test_risk.py`

## 关键公式与策略

- 到岸成本：`unit_cost + shipping_cost + unit_cost * duty_rate`
- 固定单件成本：`landed_cost + fulfillment_fee + ad_cost_per_unit`
- 变量费率：`marketplace_fee_rate + payment_fee_rate + return_rate`
- 盈亏平衡售价：`fixed_cost_per_unit / (1 - variable_rate)`
- 贡献利润：`target_price * (1 - variable_rate) - fixed_cost_per_unit`
- 利润风险：
  - 贡献利润率 `< 15%`：高风险。
  - 贡献利润率 `< 25%`：中风险。
  - 其他：低风险。

## 验证记录

命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

结果：

- 利润测算测试通过。
- 供应商评分测试通过。
- 风险分类测试通过。
- 累计后端测试 `16 passed`。

## 重要决策

- 数学和评分逻辑不交给 LLM，避免不可复现的业务判断。
- 供应商评分先采用透明规则，后续可以扩展为可配置权重。
- 风险分类以 validation issues 和利润率为第一版输入，后续可加入类目限制、侵权风险、退款阈值和平台政策。

## 下一节点

节点 05：实现工具注册中心和最小 workflow preview API，把 adapter、利润服务、供应商服务和风险服务串成可调用的后端接口。
