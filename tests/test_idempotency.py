from pathlib import Path

from pytest_httpx import HTTPXMock

from marketplace_pipeline.config import Settings
from marketplace_pipeline.crm.amocrm import AmoCRMClient
from marketplace_pipeline.crm.idempotency import (
    IdempotencyStore,
    append_idempotency_marker,
    compute_idempotency_key,
    extract_idempotency_marker,
)
from marketplace_pipeline.models import CRMTaskPayload
from marketplace_pipeline.pipeline import Pipeline


def test_compute_idempotency_key_stable() -> None:
    payload = CRMTaskPayload(title="T", description="line1\nline2")
    assert compute_idempotency_key(payload) == compute_idempotency_key(payload)


def test_compute_idempotency_key_changes_with_content() -> None:
    a = CRMTaskPayload(title="T", description="A")
    b = CRMTaskPayload(title="T", description="B")
    assert compute_idempotency_key(a) != compute_idempotency_key(b)


def test_idempotency_marker_roundtrip() -> None:
    key = "abc123"
    text = append_idempotency_marker("Title\n\nBody", key)
    assert extract_idempotency_marker(text) == key


def test_idempotency_store_persistence(tmp_path: Path) -> None:
    store_path = tmp_path / "store.json"
    store = IdempotencyStore.load(store_path)
    from marketplace_pipeline.crm.idempotency import IdempotencyRecord

    store.put(
        "key1",
        IdempotencyRecord(task_id="1", title="T", idempotency_key="key1"),
    )
    store.save(store_path)

    reloaded = IdempotencyStore.load(store_path)
    assert reloaded.get("key1") is not None
    assert reloaded.get("key1").task_id == "1"


def test_create_task_is_idempotent(tmp_path: Path) -> None:
    settings = Settings(MOCK_CRM=True)
    client = AmoCRMClient(
        settings,
        idempotency_store_path=tmp_path / "crm_idempotency.json",
    )
    payload = CRMTaskPayload(title="Test", description="- item: 100 RUB — https://example.com")

    first = client.create_task(payload)
    second = client.create_task(payload)

    assert first.reused is False
    assert second.reused is True
    assert first.task_id == second.task_id
    assert first.idempotency_key == second.idempotency_key


def test_create_task_new_content_creates_new_task(tmp_path: Path) -> None:
    settings = Settings(MOCK_CRM=True)
    client = AmoCRMClient(
        settings,
        idempotency_store_path=tmp_path / "crm_idempotency.json",
    )

    first = client.create_task(CRMTaskPayload(title="A", description="1"))
    second = client.create_task(CRMTaskPayload(title="B", description="2"))

    assert first.task_id != second.task_id
    assert first.reused is False
    assert second.reused is False


def test_amocrm_remote_reuses_existing_task(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    settings = Settings(
        MOCK_CRM=False,
        AMOCRM_SUBDOMAIN="example",
        AMOCRM_ACCESS_TOKEN="token",
    )
    payload = CRMTaskPayload(title="T", description="Product list")
    key = compute_idempotency_key(payload)
    marker_text = append_idempotency_marker(f"{payload.title}\n\n{payload.description}", key)

    httpx_mock.add_response(
        json={
            "_embedded": {
                "tasks": [{"id": 777, "text": marker_text}],
            }
        }
    )

    client = AmoCRMClient(
        settings,
        idempotency_store_path=tmp_path / "crm_idempotency.json",
    )
    result = client.create_task(payload)

    assert result.reused is True
    assert result.task_id == "777"
    assert len(httpx_mock.get_requests()) == 1


def test_pipeline_second_run_reuses_crm_tasks(tmp_path: Path) -> None:
    settings = Settings(
        MOCK_PARSER=True,
        MOCK_LLM=True,
        MOCK_CRM=True,
        DEMO_MODE=True,
        DEMO_PRODUCT_COUNT=30,
    )
    first = Pipeline(settings, output_dir=tmp_path).run()
    second = Pipeline(settings, output_dir=tmp_path).run()

    assert len(first.crm_tasks) >= 1
    assert all(task.reused is False for task in first.crm_tasks)
    assert all(task.reused is True for task in second.crm_tasks)
    assert first.crm_tasks[0].task_id == second.crm_tasks[0].task_id
