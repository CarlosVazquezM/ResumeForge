"""Pytest configuration and shared fixtures."""

import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "output_verification: tests that verify output files"
    )
    config.addinivalue_line(
        "markers", "cli_coverage: tests that verify CLI commands"
    )
    config.addinivalue_line(
        "markers", "feature_completeness: tests that check for NotImplementedError"
    )
    config.addinivalue_line(
        "markers", "critical: tests that must pass for production"
    )
