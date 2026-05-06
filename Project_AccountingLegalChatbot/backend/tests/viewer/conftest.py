# Isolated conftest — prevents parent session-scope autouse fixtures from running here.
import pytest


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """No-op override: viewer tests are pure Python and don't need the async test DB."""
    yield
