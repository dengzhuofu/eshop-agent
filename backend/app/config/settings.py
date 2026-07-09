from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Eshop Agent API"
    DEBUG: bool = False
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    LLM_MODEL: str = "deepseek-ai/DeepSeek-V3.2"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    VISION_MODEL: str = "Qwen/Qwen3-VL-32B-Instruct"


@lru_cache
def get_settings() -> Settings:
    return Settings()
