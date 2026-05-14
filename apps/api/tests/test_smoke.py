from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import smoke as smoke_module
from app.api.v1.smoke import router as smoke_router
from app.core.settings import settings
from app.middleware.exception_handlers import register_exception_handlers
from app.schemas.smoke import SmokeActionName, SmokeNotificationStatus


@pytest.fixture(autouse=True)
def reset_smoke_flag() -> Iterator[None]:
    original = {
        "ENABLE_SMOKE_TESTS": settings.ENABLE_SMOKE_TESTS,
        "RESEND_API_KEY": settings.RESEND_API_KEY,
        "RESEND_FROM_EMAIL": settings.RESEND_FROM_EMAIL,
        "SMOKE_TEST_EMAIL": settings.SMOKE_TEST_EMAIL,
        "STRIPE_SECRET_KEY": settings.STRIPE_SECRET_KEY,
        "ENABLE_STRIPE_SMOKE_TRANSACTIONS": settings.ENABLE_STRIPE_SMOKE_TRANSACTIONS,
    }
    yield
    for name, value in original.items():
        setattr(settings, name, value)


@pytest.fixture
def mock_smoke_integrations(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_notification(
        *,
        action: SmokeActionName,
        status_message: str,
    ) -> SmokeNotificationStatus:
        return SmokeNotificationStatus(
            provider="resend",
            sent=True,
            recipient=settings.SMOKE_TEST_EMAIL,
            message_id=f"email-{action}",
        )

    async def fake_stripe_check() -> None:
        return None

    async def fake_stripe_transaction() -> str:
        return "pi_smoke_test"

    monkeypatch.setattr(smoke_module, "send_smoke_notification", fake_notification)
    monkeypatch.setattr(smoke_module, "check_stripe_credentials", fake_stripe_check)
    monkeypatch.setattr(smoke_module, "create_stripe_test_transaction", fake_stripe_transaction)


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
    settings.RESEND_API_KEY = "re_test"
    settings.RESEND_FROM_EMAIL = "Freelio Smoke <smoke@example.com>"
    settings.STRIPE_SECRET_KEY = "sk_test_123"

    response = _client().get("/api/v1/smoke/config")

    assert response.status_code == 200
    body = response.json()
    required = body["data"]["required"]
    names = {item["name"] for item in required}
    smoke = body["data"]["smoke"]
    smoke_names = {item["name"] for item in smoke}

    assert body["data"]["enabled"] is True
    assert body["data"]["all_required_present"] is True
    assert names == {
        "SECRET_KEY",
        "DATABASE_URL",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
    }
    assert smoke_names == {
        "REDIS_URL",
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
        "SMOKE_TEST_EMAIL",
        "STRIPE_SECRET_KEY",
        "ENABLE_STRIPE_SMOKE_TRANSACTIONS",
    }
    assert all(set(item) == {"name", "present"} for item in required)
    assert all(set(item) == {"name", "present"} for item in smoke)


@pytest.mark.parametrize(
    ("path", "expected_status", "expected_implemented"),
    [
        ("/queue", "placeholder", False),
        ("/email", "ok", True),
        ("/pdf", "placeholder", False),
        ("/reminder", "placeholder", False),
        ("/stripe", "ok", True),
        ("/stripe/transaction", "ok", True),
    ],
)
def test_smoke_actions_send_resend_notification_on_success(
    path: str,
    expected_status: str,
    expected_implemented: bool,
    mock_smoke_integrations: None,
) -> None:
    settings.ENABLE_SMOKE_TESTS = True
    settings.RESEND_API_KEY = "re_test"
    settings.RESEND_FROM_EMAIL = "Freelio Smoke <smoke@example.com>"
    settings.SMOKE_TEST_EMAIL = "jacobmuck2004@gmail.com"
    settings.STRIPE_SECRET_KEY = "sk_test_123"
    settings.ENABLE_STRIPE_SMOKE_TRANSACTIONS = True

    response = _client().post(f"/api/v1/smoke{path}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == expected_status
    assert data["implemented"] is expected_implemented
    assert data["notification"]["provider"] == "resend"
    assert data["notification"]["sent"] is True
    assert data["notification"]["recipient"] == "jacobmuck2004@gmail.com"


def test_stripe_transaction_requires_explicit_enablement() -> None:
    settings.ENABLE_SMOKE_TESTS = True
    settings.STRIPE_SECRET_KEY = "sk_test_123"
    settings.ENABLE_STRIPE_SMOKE_TRANSACTIONS = False

    response = _client().post("/api/v1/smoke/stripe/transaction")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "stripe_smoke_transactions_disabled"


@pytest.mark.parametrize("path", ["/stripe", "/stripe/transaction"])
def test_stripe_smoke_rejects_live_secret_key(path: str) -> None:
    settings.ENABLE_SMOKE_TESTS = True
    settings.STRIPE_SECRET_KEY = "sk_live_123"
    settings.ENABLE_STRIPE_SMOKE_TRANSACTIONS = True

    response = _client().post(f"/api/v1/smoke{path}")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "stripe_live_key_rejected"
