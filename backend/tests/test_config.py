from app.config.models import MODEL_CONFIG, RETRIEVAL_CONFIG
from app.config.settings import Settings


def test_model_config_uses_siliconflow_defaults():
    assert MODEL_CONFIG["llm"]["provider"] == "siliconflow"
    assert MODEL_CONFIG["llm"]["model"] == "deepseek-ai/DeepSeek-V3.2"
    assert MODEL_CONFIG["llm"]["base_url"] == "https://api.siliconflow.cn/v1"
    assert MODEL_CONFIG["embedding"]["model"] == "BAAI/bge-m3"
    assert MODEL_CONFIG["embedding"]["dimensions"] == 1024
    assert MODEL_CONFIG["reranker"]["model"] == "BAAI/bge-reranker-v2-m3"


def test_retrieval_config_matches_prd_defaults():
    assert RETRIEVAL_CONFIG["initial_top_k"] == 20
    assert RETRIEVAL_CONFIG["rerank_top_k"] == 5
    assert RETRIEVAL_CONFIG["score_threshold"] == 0.3
    assert RETRIEVAL_CONFIG["max_refinements"] == 3


def test_settings_do_not_require_real_api_key_for_tests(monkeypatch):
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    settings = Settings()

    assert settings.SILICONFLOW_API_KEY == ""
    assert settings.SILICONFLOW_BASE_URL == "https://api.siliconflow.cn/v1"
    assert settings.LLM_MODEL == "deepseek-ai/DeepSeek-V3.2"
    assert settings.EMBEDDING_MODEL == "BAAI/bge-m3"
    assert settings.RERANKER_MODEL == "BAAI/bge-reranker-v2-m3"
