from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

JobStoreBackend = Literal["sqlite", "postgres"]
JobRunnerBackend = Literal["thread", "celery"]
CrmIdempotencyBackend = Literal["file", "redis"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
    mock_parser: bool = Field(default=False, alias="MOCK_PARSER")
    mock_llm: bool = Field(default=False, alias="MOCK_LLM")
    mock_crm: bool = Field(default=False, alias="MOCK_CRM")

    target_product_count: int = Field(default=10_000, alias="TARGET_PRODUCT_COUNT")
    demo_product_count: int = Field(default=100, alias="DEMO_PRODUCT_COUNT")

    ozon_category_path: str = Field(
        default="/category/smartfony-15502/",
        alias="OZON_CATEGORY_PATH",
    )
    ozon_api_base_url: str = Field(
        default="https://www.ozon.ru/api/composer-api.bx/page/json/v2",
        alias="OZON_API_BASE_URL",
    )
    ozon_page_size: int = Field(default=36, alias="OZON_PAGE_SIZE")
    ozon_request_timeout: float = Field(default=30.0, alias="OZON_REQUEST_TIMEOUT")

    llm_provider: str = Field(default="openai", alias="LLM_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    llm_batch_size: int = Field(default=25, alias="LLM_BATCH_SIZE")

    amocrm_subdomain: str = Field(default="", alias="AMOCRM_SUBDOMAIN")
    amocrm_access_token: str = Field(default="", alias="AMOCRM_ACCESS_TOKEN")
    amocrm_responsible_user_id: int = Field(default=0, alias="AMOCRM_RESPONSIBLE_USER_ID")
    crm_idempotency_enabled: bool = Field(default=True, alias="CRM_IDEMPOTENCY_ENABLED")
    crm_idempotency_store_path: str = Field(
        default="data/crm_idempotency.json",
        alias="CRM_IDEMPOTENCY_STORE_PATH",
    )
    crm_idempotency_backend: CrmIdempotencyBackend = Field(
        default="file",
        alias="CRM_IDEMPOTENCY_BACKEND",
    )

    http_max_retries: int = Field(default=5, alias="HTTP_MAX_RETRIES")
    http_retry_base_delay: float = Field(default=1.0, alias="HTTP_RETRY_BASE_DELAY")

    job_store_backend: JobStoreBackend = Field(default="sqlite", alias="JOB_STORE_BACKEND")
    job_db_path: str = Field(default="data/jobs.sqlite", alias="JOB_DB_PATH")
    database_url: str = Field(default="", alias="DATABASE_URL")

    job_runner_backend: JobRunnerBackend = Field(default="thread", alias="JOB_RUNNER_BACKEND")
    api_job_workers: int = Field(default=2, alias="API_JOB_WORKERS")

    redis_url: str = Field(default="", alias="REDIS_URL")
    celery_broker_url: str = Field(default="", alias="CELERY_BROKER_URL")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_json: bool = Field(default=False, alias="LOG_JSON")

    api_key: str = Field(default="", alias="API_KEY")
    api_rate_limit_per_minute: int = Field(default=60, alias="API_RATE_LIMIT_PER_MINUTE")
    job_idempotency_ttl_seconds: int = Field(default=86_400, alias="JOB_IDEMPOTENCY_TTL_SECONDS")

    otel_enabled: bool = Field(default=False, alias="OTEL_ENABLED")
    otel_service_name: str = Field(default="marketplace-pipeline", alias="OTEL_SERVICE_NAME")
    otel_exporter_otlp_endpoint: str = Field(
        default="http://localhost:4318/v1/traces",
        alias="OTEL_EXPORTER_OTLP_ENDPOINT",
    )
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    sentry_environment: str = Field(default="production", alias="SENTRY_ENVIRONMENT")

    @model_validator(mode="after")
    def validate_scale_backends(self) -> Settings:
        if self.job_store_backend == "postgres" and not self.database_url.strip():
            raise ValueError("DATABASE_URL is required when JOB_STORE_BACKEND=postgres")
        if self.job_runner_backend == "celery" and not (
            self.celery_broker_url.strip() or self.redis_url.strip()
        ):
            raise ValueError(
                "CELERY_BROKER_URL or REDIS_URL is required when JOB_RUNNER_BACKEND=celery"
            )
        if self.crm_idempotency_backend == "redis" and not self.redis_url.strip():
            raise ValueError("REDIS_URL is required when CRM_IDEMPOTENCY_BACKEND=redis")
        return self

    @property
    def collection_target(self) -> int:
        if self.demo_mode:
            return self.demo_product_count
        return self.target_product_count

    @property
    def api_auth_enabled(self) -> bool:
        return bool(self.api_key.strip())

    @property
    def job_store_label(self) -> str:
        if self.job_store_backend == "postgres":
            return "postgres"
        return self.job_db_path


def get_settings() -> Settings:
    return Settings()
