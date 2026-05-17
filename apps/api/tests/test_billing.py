from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://example")
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

from app.api.v1 import billing as billing_route
from app.api.v1.billing import router as billing_router
from app.clients.stripe_billing import (
    StripeBillingCheckoutSession,
    StripeBillingClient,
    StripeBillingCustomer,
    StripeBillingPortalSession,
)
from app.core.deps import get_current_user, get_user_scoped_db
from app.core.settings import Settings
from app.exceptions import BadRequestError, ConflictError
from app.middleware.exception_handlers import register_exception_handlers
from app.repositories import billing as billing_repo
from app.repositories.billing import BillingAccountRecord
from app.schemas.auth import AuthUser
from app.schemas.billing import BillingCheckoutResponse, BillingPortalResponse
from app.services.billing import BillingService, calculate_billable_org_count

if TYPE_CHECKING:
    from postgrest import AsyncPostgrestClient

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeStripeBilling:
    def __init__(self) -> None:
        self.customers: list[dict[str, Any]] = []
        self.checkout_sessions: list[dict[str, Any]] = []
        self.portal_sessions: list[str] = []

    async def create_customer(
        self,
        *,
        user_id: UUID,
        email: str | None,
    ) -> StripeBillingCustomer:
        self.customers.append({"user_id": user_id, "email": email})
        return StripeBillingCustomer(customer_id="cus_created")

    async def create_subscription_checkout_session(
        self,
        *,
        customer_id: str,
        user_id: UUID,
        billable_org_count: int,
    ) -> StripeBillingCheckoutSession:
        self.checkout_sessions.append(
            {
                "customer_id": customer_id,
                "user_id": user_id,
                "billable_org_count": billable_org_count,
            }
        )
        return StripeBillingCheckoutSession(
            session_id="cs_subscribe",
            checkout_url="https://checkout.stripe.com/pay/cs_subscribe",
        )

    async def create_billing_portal_session(
        self,
        *,
        customer_id: str,
    ) -> StripeBillingPortalSession:
        self.portal_sessions.append(customer_id)
        return StripeBillingPortalSession(portal_url="https://billing.stripe.com/session/bps_123")


def _db() -> AsyncPostgrestClient:
    return cast("AsyncPostgrestClient", object())


def _account(**overrides: Any) -> BillingAccountRecord:
    values = {
        "user_id": uuid4(),
        "email": "owner@example.com",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "billing_status": "free",
        "billing_price_id": None,
        "billing_current_period_end": None,
    }
    values.update(overrides)
    return BillingAccountRecord(**values)


async def _stub_billing_repo(
    monkeypatch: pytest.MonkeyPatch,
    *,
    account: BillingAccountRecord | None,
    owned_org_count: int,
    saved_customer_ids: list[str] | None = None,
) -> None:
    async def fake_get_billing_account(
        _client: AsyncPostgrestClient, *, user_id: UUID
    ) -> BillingAccountRecord | None:
        return account

    async def fake_count_owned_organizations(
        _client: AsyncPostgrestClient, *, user_id: UUID
    ) -> int:
        return owned_org_count

    async def fake_set_stripe_customer_id(
        _client: AsyncPostgrestClient, *, user_id: UUID, customer_id: str
    ) -> BillingAccountRecord:
        if saved_customer_ids is not None:
            saved_customer_ids.append(customer_id)
        return _account(
            user_id=user_id,
            email=account.email if account else None,
            stripe_customer_id=customer_id,
        )

    monkeypatch.setattr(billing_repo, "get_billing_account", fake_get_billing_account)
    monkeypatch.setattr(
        billing_repo,
        "count_owned_organizations",
        fake_count_owned_organizations,
    )
    monkeypatch.setattr(
        billing_repo,
        "set_stripe_customer_id",
        fake_set_stripe_customer_id,
    )


def test_calculate_billable_org_count() -> None:
    assert calculate_billable_org_count(0) == 0
    assert calculate_billable_org_count(1) == 0
    assert calculate_billable_org_count(2) == 1
    assert calculate_billable_org_count(4) == 3


async def test_subscribe_rejects_when_no_paid_subscription_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _account()
    stripe = FakeStripeBilling()
    await _stub_billing_repo(monkeypatch, account=account, owned_org_count=1)
    service = BillingService(_db(), stripe_billing=cast("Any", stripe))

    with pytest.raises(ConflictError) as exc_info:
        await service.create_subscription_checkout(
            user_id=account.user_id,
            user_email="fresh@example.com",
        )

    assert exc_info.value.code == "billing_not_required"
    assert stripe.customers == []
    assert stripe.checkout_sessions == []


async def test_subscribe_creates_customer_once_and_uses_server_org_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    account = _account(user_id=user_id, email="stored@example.com")
    stripe = FakeStripeBilling()
    saved_customer_ids: list[str] = []
    await _stub_billing_repo(
        monkeypatch,
        account=account,
        owned_org_count=3,
        saved_customer_ids=saved_customer_ids,
    )
    service = BillingService(_db(), stripe_billing=cast("Any", stripe))

    response = await service.create_subscription_checkout(
        user_id=user_id,
        user_email="auth@example.com",
    )

    assert response.checkout_url == "https://checkout.stripe.com/pay/cs_subscribe"
    assert stripe.customers == [{"user_id": user_id, "email": "auth@example.com"}]
    assert saved_customer_ids == ["cus_created"]
    assert stripe.checkout_sessions == [
        {
            "customer_id": "cus_created",
            "user_id": user_id,
            "billable_org_count": 2,
        }
    ]


async def test_subscribe_reuses_customer_and_rejects_existing_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    account = _account(
        user_id=user_id,
        stripe_customer_id="cus_existing",
        stripe_subscription_id="sub_existing",
        billing_status="active",
        billing_current_period_end=datetime(2026, 6, 1, tzinfo=UTC),
    )
    stripe = FakeStripeBilling()
    await _stub_billing_repo(monkeypatch, account=account, owned_org_count=3)
    service = BillingService(_db(), stripe_billing=cast("Any", stripe))

    with pytest.raises(ConflictError) as exc_info:
        await service.create_subscription_checkout(
            user_id=user_id,
            user_email="owner@example.com",
        )

    assert exc_info.value.code == "billing_subscription_exists"
    assert stripe.customers == []
    assert stripe.checkout_sessions == []


async def test_portal_requires_initialized_billing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _account(stripe_customer_id="cus_existing")
    stripe = FakeStripeBilling()
    await _stub_billing_repo(monkeypatch, account=account, owned_org_count=2)
    service = BillingService(_db(), stripe_billing=cast("Any", stripe))

    with pytest.raises(ConflictError) as exc_info:
        await service.create_billing_portal(user_id=account.user_id)

    assert exc_info.value.code == "billing_not_initialized"
    assert stripe.portal_sessions == []


async def test_portal_creates_stripe_portal_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _account(
        stripe_customer_id=" cus_existing ",
        stripe_subscription_id="sub_existing",
        billing_status="active",
    )
    stripe = FakeStripeBilling()
    await _stub_billing_repo(monkeypatch, account=account, owned_org_count=2)
    service = BillingService(_db(), stripe_billing=cast("Any", stripe))

    response = await service.create_billing_portal(user_id=account.user_id)

    assert response.portal_url == "https://billing.stripe.com/session/bps_123"
    assert stripe.portal_sessions == ["cus_existing"]


def test_subscription_checkout_payload_uses_settings_prices_and_metadata() -> None:
    app_settings = Settings(
        SECRET_KEY="test-secret",
        DATABASE_URL="postgresql://example",
        SUPABASE_URL="https://supabase.test",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role",
        STRIPE_SECRET_KEY="sk_test_123",
        STRIPE_BILLING_ADDITIONAL_ORG_PRICE_ID="price_additional_org",
        STRIPE_BILLING_BASE_PRICE_ID="price_base",
        WEB_BASE_URL="https://app.example.com/",
    )
    client = StripeBillingClient(app_settings)
    user_id = uuid4()

    payload = client._build_subscription_checkout_payload(
        customer_id="cus_123",
        user_id=user_id,
        billable_org_count=2,
        base_url="https://app.example.com",
        additional_org_price_id=client._require_additional_org_price_id(),
        base_price_id=client._optional_base_price_id(),
    )

    assert payload["mode"] == "subscription"
    assert payload["customer"] == "cus_123"
    assert payload["client_reference_id"] == str(user_id)
    assert payload["success_url"] == (
        "https://app.example.com/settings/billing/success?session_id={CHECKOUT_SESSION_ID}"
    )
    assert payload["cancel_url"] == "https://app.example.com/settings/billing"
    assert payload["line_items[0][price]"] == "price_base"
    assert payload["line_items[0][quantity]"] == "1"
    assert payload["line_items[1][price]"] == "price_additional_org"
    assert payload["line_items[1][quantity]"] == "1"
    assert payload["line_items[2][price]"] == "price_additional_org"
    assert payload["line_items[2][quantity]"] == "1"
    assert payload["metadata[source]"] == "freelio_saas_billing"
    assert payload["metadata[billable_org_count]"] == "2"
    assert payload["subscription_data[metadata][user_id]"] == str(user_id)


async def test_missing_billing_price_config_returns_bad_request() -> None:
    app_settings = Settings(
        SECRET_KEY="test-secret",
        DATABASE_URL="postgresql://example",
        SUPABASE_URL="https://supabase.test",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role",
        STRIPE_SECRET_KEY="sk_test_123",
        WEB_BASE_URL="https://app.example.com",
    )
    client = StripeBillingClient(app_settings)

    with pytest.raises(BadRequestError) as exc_info:
        await client.create_subscription_checkout_session(
            customer_id="cus_123",
            user_id=uuid4(),
            billable_org_count=1,
        )

    assert exc_info.value.code == "billing_price_not_configured"


def test_subscribe_route_ignores_client_supplied_billing_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    calls: list[dict[str, Any]] = []

    class RouteBillingService:
        def __init__(self, db: object, *, stripe_billing: object) -> None:
            self.db = db
            self.stripe_billing = stripe_billing

        async def create_subscription_checkout(
            self,
            *,
            user_id: UUID,
            user_email: str | None,
        ) -> BillingCheckoutResponse:
            calls.append({"user_id": user_id, "user_email": user_email})
            return BillingCheckoutResponse(checkout_url="https://checkout.stripe.com/pay/cs_route")

    monkeypatch.setattr(billing_route, "BillingService", RouteBillingService)

    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(billing_router, prefix="/api/v1")
    test_app.dependency_overrides[get_current_user] = lambda: AuthUser(
        user_id=user_id,
        email="owner@example.com",
    )
    test_app.dependency_overrides[get_user_scoped_db] = lambda: object()

    response = TestClient(test_app).post(
        "/api/v1/billing/subscribe",
        json={
            "org_count": 99,
            "price_id": "price_attacker",
            "stripe_customer_id": "cus_attacker",
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == {"checkout_url": "https://checkout.stripe.com/pay/cs_route"}
    assert calls == [{"user_id": user_id, "user_email": "owner@example.com"}]


def test_portal_route_returns_portal_url(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    calls: list[UUID] = []

    class RouteBillingService:
        def __init__(self, db: object, *, stripe_billing: object) -> None:
            self.db = db
            self.stripe_billing = stripe_billing

        async def create_billing_portal(
            self,
            *,
            user_id: UUID,
        ) -> BillingPortalResponse:
            calls.append(user_id)
            return BillingPortalResponse(portal_url="https://billing.stripe.com/session/bps_route")

    monkeypatch.setattr(billing_route, "BillingService", RouteBillingService)

    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(billing_router, prefix="/api/v1")
    test_app.dependency_overrides[get_current_user] = lambda: AuthUser(
        user_id=user_id,
        email="owner@example.com",
    )
    test_app.dependency_overrides[get_user_scoped_db] = lambda: object()

    response = TestClient(test_app).post("/api/v1/billing/portal")

    assert response.status_code == 200
    assert response.json()["data"] == {"portal_url": "https://billing.stripe.com/session/bps_route"}
    assert calls == [user_id]
