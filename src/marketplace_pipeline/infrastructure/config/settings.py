from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    http_max_retries: int = Field(default=5, alias="HTTP_MAX_RETRIES")
    http_retry_base_delay: float = Field(default=1.0, alias="HTTP_RETRY_BASE_DELAY")
    job_db_path: str = Field(default="data/jobs.sqlite", alias="JOB_DB_PATH")
    api_job_workers: int = Field(default=2, alias="API_JOB_WORKERS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def collection_target(self) -> int:
        if self.demo_mode:
            return self.demo_product_count
        return self.target_product_count


def get_settings() -> Settings:
    return Settings()
