import pytest
from fastapi.testclient import TestClient

from collagent.api.auth import get_current_user_id
from collagent.api.main import app

TEST_USER = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER
    yield TestClient(app)
    app.dependency_overrides.clear()
