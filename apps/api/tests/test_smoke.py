from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.smoke import router as smoke_router
from app.core.settings import settings
from app.middleware.exception_handlers import register_exception_handlers


@pytest.fixture(autouse=True)
def reset_smoke_flag() -> Iterator[None]:
    original = settings.ENABLE_SMOKE_TESTS
    yield
    settings.ENABLE_SMOKE_TESTS = original


def _client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(smoke_router, prefix="/api/v1")
    return TestClient(app)


def test_smoke_config_returns_404_when_disabled() -> None:
    settings.ENABLE_SMOKE_TESTS = False

    response = _client().get("/api/v1/smoke/config")

    assert response.status_code == 404


def test_smoke_config_returns_presence_without_secret_values() -> None:
    settings.ENABLE_SMOKE_TESTS = True

    response = _client().get("/api/v1/smoke/config")

    assert response.status_code == 200
    body = response.json()
    required = body["data"]["required"]
    names = {item["name"] for item in required}

    assert body["data"]["enabled"] is True
    assert body["data"]["all_required_present"] is True
    assert names == {
        "SECRET_KEY",
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    }
    assert all(set(item) == {"name", "present"} for item in required)


@pytest.mark.parametrize("path", ["/queue", "/email", "/pdf", "/reminder"])
def test_smoke_actions_are_placeholders(path: str) -> None:
    settings.ENABLE_SMOKE_TESTS = True

    response = _client().post(f"/api/v1/smoke{path}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "placeholder"
    assert data["implemented"] is False
