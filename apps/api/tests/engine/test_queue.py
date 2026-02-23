"""Unit tests for Celery app configuration.

Validates that the Celery app is configured with the expected
serialization, timing, and reliability settings.
"""

from app.engine.queue import celery_app


class TestCeleryAppConfig:
    """Verify Celery app settings match production requirements."""

    def test_celery_app_name(self):
        assert celery_app.main == "coreloop"

    def test_json_serializer(self):
        assert celery_app.conf.task_serializer == "json"

    def test_accept_content(self):
        assert "json" in celery_app.conf.accept_content

    def test_result_serializer(self):
        assert celery_app.conf.result_serializer == "json"

    def test_utc_enabled(self):
        assert celery_app.conf.enable_utc is True

    def test_timezone(self):
        assert celery_app.conf.timezone == "UTC"

    def test_acks_late_enabled(self):
        """Tasks are acknowledged after completion to prevent loss."""
        assert celery_app.conf.task_acks_late is True

    def test_prefetch_multiplier(self):
        """Workers only prefetch one task at a time for fairness."""
        assert celery_app.conf.worker_prefetch_multiplier == 1

    def test_soft_time_limit(self):
        # Global default is intentionally short (Beat/lightweight tasks).
        # Long-running tasks like execute_run override this per-task.
        assert celery_app.conf.task_soft_time_limit == 120

    def test_hard_time_limit(self):
        assert celery_app.conf.task_time_limit == 180
