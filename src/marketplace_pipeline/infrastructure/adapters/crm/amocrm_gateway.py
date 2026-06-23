from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from marketplace_pipeline.domain.exceptions import CrmConfigurationError
from marketplace_pipeline.domain.models.crm_task import CrmTaskOutcome, CrmTaskRequest
from marketplace_pipeline.domain.ports.idempotency_store import (
    IdempotencyRecord,
    IdempotencyStorePort,
)
from marketplace_pipeline.domain.services.idempotency_policy import (
    append_idempotency_marker,
    compute_task_idempotency_key,
    extract_idempotency_marker,
)
from marketplace_pipeline.infrastructure.adapters.crm.file_idempotency_store import (
    FileIdempotencyStore,
)
from marketplace_pipeline.infrastructure.config.settings import Settings
from marketplace_pipeline.infrastructure.http.http_client import HttpClient

logger = logging.getLogger(__name__)


class AmoCrmGateway:
    """Infrastructure adapter: AmoCRM REST v4 with idempotent task creation."""

    def __init__(
        self,
        settings: Settings,
        idempotency_store: IdempotencyStorePort,
        http_client: HttpClient | None = None,
    ) -> None:
        self._settings = settings
        self._store = idempotency_store
        self._http = http_client or HttpClient(
            max_retries=settings.http_max_retries,
            base_delay=settings.http_retry_base_delay,
        )

    def create_task(self, task: CrmTaskRequest) -> CrmTaskOutcome:
        idempotency_key = compute_task_idempotency_key(task)

        existing = self._find_existing(idempotency_key)
        if existing is not None:
            logger.info(
                "CRM task reused (idempotent): key=%s task_id=%s title=%s",
                idempotency_key[:12],
                existing.task_id,
                task.title,
            )
            return CrmTaskOutcome(
                task_id=existing.task_id,
                title=task.title,
                mocked=self._settings.mock_crm,
                reused=True,
                idempotency_key=idempotency_key,
            )

        if self._settings.mock_crm:
            outcome = self._create_mock_task(task, idempotency_key)
        else:
            outcome = self._create_remote_task(task, idempotency_key)

        self._store.put(
            idempotency_key,
            IdempotencyRecord(
                task_id=outcome.task_id,
                title=task.title,
                idempotency_key=idempotency_key,
            ),
        )
        if self._settings.crm_idempotency_enabled:
            self._store.save()
        return outcome

    def _find_existing(self, idempotency_key: str) -> IdempotencyRecord | None:
        if not self._settings.crm_idempotency_enabled:
            return None

        cached = self._store.get(idempotency_key)
        if cached is not None:
            return cached

        if self._settings.mock_crm:
            return None

        remote_task_id = self._find_remote_task_by_marker(idempotency_key)
        if remote_task_id is None:
            return None

        record = IdempotencyRecord(
            task_id=remote_task_id,
            title="",
            idempotency_key=idempotency_key,
        )
        self._store.put(idempotency_key, record)
        if self._settings.crm_idempotency_enabled:
            self._store.save()
        return record

    def _create_mock_task(self, task: CrmTaskRequest, idempotency_key: str) -> CrmTaskOutcome:
        task_id = f"mock-task-{idempotency_key[:12]}"
        logger.info("MOCK_CRM task created: id=%s title=%s", task_id, task.title)
        return CrmTaskOutcome(
            task_id=task_id,
            title=task.title,
            mocked=True,
            idempotency_key=idempotency_key,
        )

    def _create_remote_task(self, task: CrmTaskRequest, idempotency_key: str) -> CrmTaskOutcome:
        if not self._settings.amocrm_subdomain or not self._settings.amocrm_access_token:
            raise CrmConfigurationError("AMOCRM_SUBDOMAIN and AMOCRM_ACCESS_TOKEN are required")

        complete_till = int((datetime.now(tz=UTC) + timedelta(days=3)).timestamp())
        body_text = append_idempotency_marker(
            f"{task.title}\n\n{task.description}",
            idempotency_key,
        )
        payload: dict[str, object] = {
            "text": body_text,
            "complete_till": complete_till,
        }
        if self._settings.amocrm_responsible_user_id:
            payload["responsible_user_id"] = self._settings.amocrm_responsible_user_id

        url = f"https://{self._settings.amocrm_subdomain}.amocrm.ru/api/v4/tasks"
        response = self._http.post(
            url,
            headers={
                "Authorization": f"Bearer {self._settings.amocrm_access_token}",
                "Content-Type": "application/json",
            },
            json=[payload],
        )
        data = response.json()
        logger.info("AmoCRM response: %s", data)
        embedded = data.get("_embedded", {}).get("tasks", [])
        if not embedded:
            raise ValueError(f"Unexpected AmoCRM response: {data}")

        return CrmTaskOutcome(
            task_id=str(embedded[0]["id"]),
            title=task.title,
            idempotency_key=idempotency_key,
        )

    def _find_remote_task_by_marker(self, idempotency_key: str) -> str | None:
        url = f"https://{self._settings.amocrm_subdomain}.amocrm.ru/api/v4/tasks"
        page = 1
        while page <= 5:
            response = self._http.get(
                url,
                headers={"Authorization": f"Bearer {self._settings.amocrm_access_token}"},
                params={"limit": 250, "page": page, "order[updated_at]": "desc"},
            )
            tasks = response.json().get("_embedded", {}).get("tasks", [])
            if not tasks:
                break
            for item in tasks:
                if extract_idempotency_marker(str(item.get("text", ""))) == idempotency_key:
                    return str(item["id"])
            if len(tasks) < 250:
                break
            page += 1
        return None


def build_idempotency_store(settings: Settings, path: Path | None = None) -> FileIdempotencyStore:
    return FileIdempotencyStore(
        path or Path(settings.crm_idempotency_store_path),
        enabled=settings.crm_idempotency_enabled,
    )
