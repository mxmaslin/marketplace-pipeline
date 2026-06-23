from __future__ import annotations

from dataclasses import dataclass

from marketplace_pipeline.domain.exceptions import PipelineConfigurationError


@dataclass(frozen=True)
class PipelinePrerequisites:
    mock_llm: bool
    mock_crm: bool
    openai_api_key: str
    amocrm_subdomain: str
    amocrm_access_token: str


def validate_pipeline_prerequisites(prerequisites: PipelinePrerequisites) -> None:
    """Fail fast before enqueueing a job when required credentials are missing."""
    errors: list[str] = []
    if not prerequisites.mock_llm and not prerequisites.openai_api_key.strip():
        errors.append("OPENAI_API_KEY is required when MOCK_LLM=false")
    if not prerequisites.mock_crm:
        if not prerequisites.amocrm_subdomain.strip():
            errors.append("AMOCRM_SUBDOMAIN is required when MOCK_CRM=false")
        if not prerequisites.amocrm_access_token.strip():
            errors.append("AMOCRM_ACCESS_TOKEN is required when MOCK_CRM=false")
    if errors:
        raise PipelineConfigurationError("; ".join(errors))
