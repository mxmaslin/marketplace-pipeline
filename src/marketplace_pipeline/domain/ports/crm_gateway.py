from __future__ import annotations

from typing import Protocol

from marketplace_pipeline.domain.models.crm_task import CrmTaskOutcome, CrmTaskRequest


class CrmGatewayPort(Protocol):
    def create_task(self, task: CrmTaskRequest) -> CrmTaskOutcome: ...
