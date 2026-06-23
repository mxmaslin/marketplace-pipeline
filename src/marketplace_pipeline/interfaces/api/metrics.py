"""Simple in-process metrics with optional Redis aggregation for multi-node."""

from __future__ import annotations

import threading

_REDIS_KEYS = {
    "submitted": "metrics:pipeline_jobs_submitted",
    "completed": "metrics:pipeline_jobs_completed",
    "failed": "metrics:pipeline_jobs_failed",
}


class MetricsRegistry:
    def __init__(self, *, redis_url: str | None = None) -> None:
        self._lock = threading.Lock()
        self.jobs_submitted = 0
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.http_requests = 0
        self._http_duration_ms_sum = 0.0
        self._http_duration_ms_count = 0
        self._job_duration_seconds_sum = 0.0
        self._job_duration_seconds_count = 0
        self._redis = None
        if redis_url:
            import redis

            self._redis = redis.from_url(redis_url, decode_responses=True)

    def _redis_incr(self, key: str) -> None:
        if self._redis is not None:
            self._redis.incr(key)

    def _redis_get_int(self, key: str) -> int:
        if self._redis is None:
            return 0
        value = self._redis.get(key)
        return int(value) if value is not None else 0

    def _job_counter(self, local: int, redis_key: str) -> int:
        if self._redis is not None:
            return self._redis_get_int(redis_key)
        return local

    def inc_submitted(self) -> None:
        if self._redis is not None:
            self._redis_incr(_REDIS_KEYS["submitted"])
            return
        with self._lock:
            self.jobs_submitted += 1

    def inc_completed(self) -> None:
        if self._redis is not None:
            self._redis_incr(_REDIS_KEYS["completed"])
            return
        with self._lock:
            self.jobs_completed += 1

    def inc_failed(self) -> None:
        if self._redis is not None:
            self._redis_incr(_REDIS_KEYS["failed"])
            return
        with self._lock:
            self.jobs_failed += 1

    def inc_http(self) -> None:
        with self._lock:
            self.http_requests += 1

    def observe_http_duration_ms(self, duration_ms: float) -> None:
        with self._lock:
            self._http_duration_ms_sum += duration_ms
            self._http_duration_ms_count += 1

    def observe_job_duration_seconds(self, duration_seconds: float) -> None:
        with self._lock:
            self._job_duration_seconds_sum += duration_seconds
            self._job_duration_seconds_count += 1

    def render_prometheus(self) -> str:
        with self._lock:
            submitted = self._job_counter(self.jobs_submitted, _REDIS_KEYS["submitted"])
            completed = self._job_counter(self.jobs_completed, _REDIS_KEYS["completed"])
            failed = self._job_counter(self.jobs_failed, _REDIS_KEYS["failed"])
            http_avg = (
                self._http_duration_ms_sum / self._http_duration_ms_count
                if self._http_duration_ms_count
                else 0.0
            )
            job_avg = (
                self._job_duration_seconds_sum / self._job_duration_seconds_count
                if self._job_duration_seconds_count
                else 0.0
            )
            lines = [
                "# HELP pipeline_jobs_submitted_total Jobs accepted via API",
                "# TYPE pipeline_jobs_submitted_total counter",
                f"pipeline_jobs_submitted_total {submitted}",
                "# HELP pipeline_jobs_completed_total Jobs finished successfully",
                "# TYPE pipeline_jobs_completed_total counter",
                f"pipeline_jobs_completed_total {completed}",
                "# HELP pipeline_jobs_failed_total Jobs failed",
                "# TYPE pipeline_jobs_failed_total counter",
                f"pipeline_jobs_failed_total {failed}",
                "# HELP http_requests_total HTTP requests served",
                "# TYPE http_requests_total counter",
                f"http_requests_total {self.http_requests}",
                "# HELP http_request_duration_ms_avg Average HTTP request duration (ms)",
                "# TYPE http_request_duration_ms_avg gauge",
                f"http_request_duration_ms_avg {http_avg:.4f}",
                "# HELP pipeline_job_duration_seconds_avg Average job duration (seconds)",
                "# TYPE pipeline_job_duration_seconds_avg gauge",
                f"pipeline_job_duration_seconds_avg {job_avg:.4f}",
            ]
        return "\n".join(lines) + "\n"
