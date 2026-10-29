"""应用配置：统一从环境变量读取，禁止在业务代码中散落硬编码配置。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 数据库
    database_url: str = "postgresql+asyncpg://knowdesk:knowdesk@localhost:5432/knowdesk"
    database_url_sync: str = "postgresql+psycopg://knowdesk:knowdesk@localhost:5432/knowdesk"

    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection: str = "knowdesk_chunks"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "knowdesk-documents"
    minio_secure: bool = False

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # LLM
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_backup_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2  # 网络层错误（连接重置/中断）的重试次数

    # Embedding / Rerank provider
    embedding_provider: str = "fake"  # fake | sentence_transformer | openai_compat
    embedding_model: str = "BAAI/bge-m3"
    embedding_base_url: str = ""  # openai_compat 时必填（如 DashScope compatible-mode）
    embedding_api_key: str = ""
    embedding_dim: int = 1024  # openai_compat 返回维度（text-embedding-v4=1024）
    rerank_provider: str = "fake"  # fake | sentence_transformer
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    # Agent 熔断
    agent_max_steps: int = 8        # LangGraph 节点执行上限（安全熔断）
    agent_max_rounds: int = 2       # 证据不足时的最大改写重检轮数
    agent_max_tokens: int = 8192
    agent_max_seconds: int = 60

    # 审计
    audit_retention_days: int = 180

    # 检索
    retrieve_top_k: int = 8
    rerank_top_k: int = 5
    evidence_score_threshold: float = 0.20


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
