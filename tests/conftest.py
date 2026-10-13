"""Pytest fixtures for the Autonomous Finance Clerk test suite."""

import pytest
import os
import sys

# Ensure project root is in sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from company_system.setup_db import reset_database
import config


@pytest.fixture(autouse=True)
def clean_database():
    """Reset the database to clean seed state before each test."""
    reset_database(config.DB_PATH)
    yield
