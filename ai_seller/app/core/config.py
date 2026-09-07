"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = Field(default="development", description="Application environment")
    debug: bool = Field(default=True, description="Debug mode")
    secret_key: str = Field(default="change-me", description="Secret key for security")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_seller",
        description="Database connection URL",
    )
    database_sync_url: Optional[str] = Field(
        default=None, description="Synchronous database connection URL"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis URL")
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_db: int = Field(default=0, description="Redis database")

    # Qdrant
    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant URL")
    qdrant_api_key: Optional[str] = Field(default=None, description="Qdrant API key")
    qdrant_timeout: int = Field(default=30, description="Qdrant timeout in seconds")
    qdrant_sales_collection: str = Field(
        default="sales_knowledge", description="Qdrant collection for sales RAG"
    )
    qdrant_knowledge_collection: str = Field(
        default="product_knowledge", description="Qdrant collection for knowledge RAG"
    )

    # LLM Provider
    llm_provider: str = Field(default="gigachat", description="Default LLM provider")
    llm_primary: Optional[str] = Field(
        default=None, description="Primary LLM provider (falls back to llm_provider)"
    )
    llm_fallback: Optional[str] = Field(
        default=None, description="Fallback LLM provider (defaults to the other one)"
    )

    # Ollama
    ollama_base_url: str = Field(
        default="http://localhost:11434", description="Ollama base URL"
    )
    ollama_default_model: str = Field(
        default="llama3.2:3b", description="Default Ollama model"
    )

    # GigaChat
    gigachat_client_id: Optional[str] = Field(default=None, description="GigaChat client id")
    gigachat_client_secret: Optional[str] = Field(
        default=None, description="GigaChat client secret"
    )
    gigachat_auth_key: Optional[str] = Field(
        default=None,
        description="Pre-encoded GigaChat Basic credential "
        "(base64 of client_id:client_secret)",
    )
    gigachat_api_key: Optional[str] = Field(
        default=None, description="Legacy GigaChat credential"
    )
    gigachat_url: str = Field(
        default="https://gigachat.devices.sberbank.ru/api/v1",
        description="GigaChat API URL",
    )
    gigachat_auth_url: str = Field(
        default="https://ngw.devices.sberbank.ru/api/v2/oauth",
        description="GigaChat OAuth URL",
    )
    gigachat_scope: str = Field(
        default="GIGACHAT_API_PERS", description="GigaChat OAuth scope"
    )
    gigachat_model: str = Field(default="GigaChat", description="Default GigaChat model")

    # Telegram
    telegram_bot_token: Optional[str] = Field(default=None, description="Telegram bot token")
    telegram_webhook_url: Optional[str] = Field(
        default=None, description="Telegram webhook URL"
    )
    telegram_webhook_secret: Optional[str] = Field(
        default=None, description="Telegram webhook secret"
    )

    # Application
    shop_id: str = Field(default="default-shop", description="Default shop ID")
    default_language: str = Field(default="ru", description="Default language")
    default_currency: str = Field(default="RUB", description="Default currency")

    # AI Agent
    agent_name: str = Field(default="AI Seller", description="AI agent name")
    agent_tone: str = Field(default="professional", description="AI agent tone")
    agent_temperature: float = Field(default=0.7, description="LLM temperature")
    agent_max_tokens: int = Field(default=2048, description="Maximum tokens for LLM")
    agent_rag_top_k: int = Field(default=5, description="RAG top K results")

    # RAG
    rag_enabled: bool = Field(default=True, description="Enable RAG")
    sales_rag_enabled: bool = Field(default=True, description="Enable Sales RAG")
    embedding_model: str = Field(
        default="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        description="Embedding model name",
    )
    reranker_model: str = Field(
        default="BAAI/bge-reranker-base", description="Reranker model name"
    )

    # Rate Limiting
    rate_limit_requests: int = Field(default=100, description="Rate limit requests")
    rate_limit_period: int = Field(default=60, description="Rate limit period in seconds")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Logging format")

    # Security
    jwt_secret_key: str = Field(
        default="jwt-secret-key-change-me", description="JWT secret key"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expire_minutes: int = Field(default=30, description="JWT expiration in minutes")

    # Widget
    widget_api_key: Optional[str] = Field(default=None, description="Widget API key")

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """Validate application environment."""
        valid_envs = {"development", "staging", "production", "testing"}
        if v.lower() not in valid_envs:
            raise ValueError(f"app_env must be one of {valid_envs}")
        return v.lower()

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate LLM provider."""
        valid_providers = {"ollama", "gigachat", "openai", "claude", "deepseek"}
        if v.lower() not in valid_providers:
            raise ValueError(f"llm_provider must be one of {valid_providers}")
        return v.lower()

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env.lower() == "production"

    @property
    def is_debug(self) -> bool:
        """Check if debug mode is enabled."""
        return self.debug and not self.is_production


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()
