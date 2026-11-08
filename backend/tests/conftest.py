import warnings

import pytest
from fastapi.testclient import TestClient

from app.config.settings import settings
from app.main import app

warnings.filterwarnings("ignore", category=DeprecationWarning)


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def _relax_rate_limits_for_the_test_session():
    """Give the suite headroom that a live service must not have.

    Every TestClient request arrives from one client address, so a full run spends more
    of the per-minute auth and request budgets than a single user ever would. The limits
    themselves are still asserted directly: `test_request_guard_rate_limit_is_retryable`
    builds its own app with an explicit budget, and
    `test_general_rate_limit_default_is_unchanged_and_operator_configurable` checks the
    shipped defaults, so raising the budget here cannot hide a regression in the guard.
    """
    previous = (settings.auth_rate_limit_per_minute, settings.general_rate_limit_per_minute)
    object.__setattr__(settings, "auth_rate_limit_per_minute", 100000)
    object.__setattr__(settings, "general_rate_limit_per_minute", 100000)
    yield
    object.__setattr__(settings, "auth_rate_limit_per_minute", previous[0])
    object.__setattr__(settings, "general_rate_limit_per_minute", previous[1])
