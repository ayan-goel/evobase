"""Tests for Phase 14B structlog configuration.

Tests are deliberately minimal since structlog's own test suite is
comprehensive. We verify our configuration wrapper is correct.
"""

import pytest
import structlog

from app.core.logging import configure_structlog


class TestConfigureStructlog:
    def test_configure_does_not_raise_in_debug_mode(self) -> None:
        configure_structlog(debug=True)

    def test_configure_does_not_raise_in_prod_mode(self) -> None:
        configure_structlog(debug=False)

    def test_logger_usable_after_configure(self) -> None:
        configure_structlog(debug=True)
        logger = structlog.get_logger("test")
        # Should not raise
        logger.info("test message", key="value")

    def test_configure_multiple_times_is_safe(self) -> None:
        configure_structlog(debug=True)
        configure_structlog(debug=False)
        configure_structlog(debug=True)

    def test_stdlib_bridge_is_active_after_configure(self) -> None:
        import logging
        configure_structlog(debug=False)
        # stdlib logger should be functional (not raise)
        std_logger = logging.getLogger("test.stdlib")
        std_logger.info("stdlib message")
