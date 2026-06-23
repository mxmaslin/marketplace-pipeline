"""Simple in-process metrics for demo / HR review."""

from __future__ import annotations

import threading


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.jobs_submitted = 0
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.http_requests = 0

    def inc_submitted(self) -> None:
        with self._lock:
            self.jobs_submitted += 1

    def inc_completed(self) -> None:
        with self._lock:
            self.jobs_completed += 1

    def inc_failed(self) -> None:
        with self._lock:
            self.jobs_failed += 1

    def inc_http(self) -> None:
        with self._lock:
            self.http_requests += 1

    def render_prometheus(self) -> str:
        with self._lock:
            lines = [
                "# HELP pipeline_jobs_submitted_total Jobs accepted via API",
                "# TYPE pipeline_jobs_submitted_total counter",
                f"pipeline_jobs_submitted_total {self.jobs_submitted}",
                "# HELP pipeline_jobs_completed_total Jobs finished successfully",
                "# TYPE pipeline_jobs_completed_total counter",
                f"pipeline_jobs_completed_total {self.jobs_completed}",
                "# HELP pipeline_jobs_failed_total Jobs failed",
                "# TYPE pipeline_jobs_failed_total counter",
                f"pipeline_jobs_failed_total {self.jobs_failed}",
                "# HELP http_requests_total HTTP requests served",
                "# TYPE http_requests_total counter",
                f"http_requests_total {self.http_requests}",
            ]
        return "\n".join(lines) + "\n"
