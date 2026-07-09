MODEL_CONFIG = {
    "llm": {
        "provider": "siliconflow",
        "model": "deepseek-ai/DeepSeek-V3.2",
        "base_url": "https://api.siliconflow.cn/v1",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "embedding": {
        "provider": "siliconflow",
        "model": "BAAI/bge-m3",
        "dimensions": 1024,
    },
    "reranker": {
        "provider": "siliconflow",
        "model": "BAAI/bge-reranker-v2-m3",
        "top_n": 5,
    },
    "vision": {
        "provider": "siliconflow",
        "model": "Qwen/Qwen3-VL-32B-Instruct",
    },
}

RETRIEVAL_CONFIG = {
    "initial_top_k": 20,
    "rerank_top_k": 5,
    "score_threshold": 0.3,
    "max_refinements": 3,
}

