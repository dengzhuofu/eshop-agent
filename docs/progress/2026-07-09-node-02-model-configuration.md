# 节点 02：统一大模型与 RAG 模型配置

时间：2026-07-09  
提交：`b1cb976`  
状态：已完成

## 本节点目标

- 将 PRD 中的大模型配置落到后端配置层。
- 统一 SiliconFlow-compatible LLM、embedding、reranker、vision 模型默认值。
- 确保测试环境不依赖真实 API key。

## 已完成内容

- 新增 `backend/app/config/models.py`：
  - LLM provider：`siliconflow`
  - LLM model：`deepseek-ai/DeepSeek-V3.2`
  - Base URL：`https://api.siliconflow.cn/v1`
  - Embedding model：`BAAI/bge-m3`
  - Embedding dimensions：`1024`
  - Reranker model：`BAAI/bge-reranker-v2-m3`
  - Vision model：`Qwen/Qwen3-VL-32B-Instruct`
- 新增 `backend/app/config/settings.py`：
  - 通过环境变量读取 `SILICONFLOW_API_KEY`。
  - 默认 API key 为空，保证单元测试不需要真实密钥。
  - 预留 `LLM_MODEL`、`EMBEDDING_MODEL`、`RERANKER_MODEL`、`VISION_MODEL` 环境变量。
- 新增 `backend/tests/test_config.py`，覆盖模型默认值、RAG 检索默认值和无 API key 场景。

## 验证记录

命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_config.py tests/test_health.py -v
```

结果：

- `tests/test_config.py::test_model_config_uses_siliconflow_defaults PASSED`
- `tests/test_config.py::test_retrieval_config_matches_prd_defaults PASSED`
- `tests/test_config.py::test_settings_do_not_require_real_api_key_for_tests PASSED`
- `tests/test_health.py::test_health_endpoint_returns_service_status PASSED`
- `4 passed`

## 重要决策

- 不在代码、README 或 PRD 中写入真实 API key。
- 所有后续 Agent、RAG、评估器和工具层都应从统一配置读取模型信息，避免散落硬编码。
- 测试默认使用空 API key，后续真实 SiliconFlow 调用只放在集成测试或手动验证中。

## 下一节点

节点 03：建立领域 schema 和 mock marketplace adapters，实现 Amazon-like、Shopify-like、TikTokShop-like 三个平台的差异化 Listing 校验规则。
