from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://example")
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

from app.api.v1 import stripe_connect as stripe_connect_route
from app.api.v1.stripe_connect import router as stripe_connect_router
from app.clients.stripe_connect import (
    STRIPE_ACCOUNT_LINKS_URL,
    StripeAccountLink,
    StripeConnectAccount,
    StripeConnectClient,
)
from app.core.deps import UserContext, get_org_context, get_user_scoped_db
from app.core.permissions import OrgRole
from app.core.settings import Settings
from app.exceptions import ForbiddenError
from app.middleware.exception_handlers import register_exception_handlers
from app.repositories import org as org_repo
from app.repositories.org import StripeConnectOrgRecord
from app.schemas.stripe_connect import StripeConnectOnboardResponse
from app.services.stripe_connect import StripeConnectService

if TYPE_CHECKING:
    from postgrest import AsyncPostgrestClient

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeStripeConnect:
    def __init__(self) -> None:
        self.created_accounts: list[dict[str, Any]] = []
        self.account_links: list[str] = []

    async def create_express_account(
        self,
        *,
        org_id: UUID,
        org_name: str,
    ) -> StripeConnectAccount:
        self.created_accounts.append({"org_id": org_id, "org_name": org_name})
        return StripeConnectAccount(
            account_id="acct_created",
            charges_enabled=False,
            payouts_enabled=False,
            details_submitted=False,
        )

    async def create_account_link(self, *, account_id: str) -> StripeAccountLink:
        self.account_links.append(account_id)
        return StripeAccountLink(url=f"https://connect.stripe.com/setup/{account_id}")


def _db() -> AsyncPostgrestClient:
    return cast("AsyncPostgrestClient", object())


def _org_record(**overrides: Any) -> StripeConnectOrgRecord:
    values = {
        "org_id": uuid4(),
        "name": "Freelio Studio",
        "stripe_connect_account_id": None,
        "stripe_connect_onboarding_complete": False,
        "stripe_connect_charges_enabled": False,
        "stripe_connect_payouts_enabled": False,
        "stripe_connect_details_submitted": False,
    }
    values.update(overrides)
    return StripeConnectOrgRecord(**values)


async def test_onboarding_creates_account_once_and_returns_account_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = _org_record()
    stripe = FakeStripeConnect()
    saved_account_ids: list[str] = []

    async def fake_get_membership(
        _client: AsyncPostgrestClient, *, org_id: UUID, user_id: UUID
    ) -> OrgRole | None:
        return OrgRole.ADMIN

    async def fake_get_stripe_connect_org(
        _client: AsyncPostgrestClient, *, org_id: UUID
    ) -> StripeConnectOrgRecord | None:
        return org

    async def fake_set_stripe_connect_account_id(
        _client: AsyncPostgrestClient, *, org_id: UUID, account_id: str
    ) -> StripeConnectOrgRecord:
        saved_account_ids.append(account_id)
        return _org_record(
            org_id=org_id,
            stripe_connect_account_id=account_id,
        )

    monkeypatch.setattr(org_repo, "get_membership", fake_get_membership)
    monkeypatch.setattr(org_repo, "get_stripe_connect_org", fake_get_stripe_connect_org)
    monkeypatch.setattr(
        org_repo,
        "set_stripe_connect_account_id",
        fake_set_stripe_connect_account_id,
    )
    service = StripeConnectService(_db(), stripe_connect=cast("Any", stripe))

    response = await service.create_onboarding_link(
        org_id=org.org_id,
        user_id=uuid4(),
    )

    assert response.onboarding_url == "https://connect.stripe.com/setup/acct_created"
    assert response.stripe_connect_account_id == "acct_created"
    assert response.onboarding_required is True
    assert stripe.created_accounts == [{"org_id": org.org_id, "org_name": org.name}]
    assert stripe.account_links == ["acct_created"]
    assert saved_account_ids == ["acct_created"]


async def test_onboarding_reuses_existing_account_and_creates_fresh_link(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = _org_record(
        stripe_connect_account_id="acct_existing",
        stripe_connect_onboarding_complete=True,
    )
    stripe = FakeStripeConnect()

    async def fake_get_membership(
        _client: AsyncPostgrestClient, *, org_id: UUID, user_id: UUID
    ) -> OrgRole | None:
        return OrgRole.OWNER

    async def fake_get_stripe_connect_org(
        _client: AsyncPostgrestClient, *, org_id: UUID
    ) -> StripeConnectOrgRecord | None:
        return org

    async def fake_set_stripe_connect_account_id(
        _client: AsyncPostgrestClient, *, org_id: UUID, account_id: str
    ) -> StripeConnectOrgRecord:
        raise AssertionError("existing Stripe account should be reused")

    monkeypatch.setattr(org_repo, "get_membership", fake_get_membership)
    monkeypatch.setattr(org_repo, "get_stripe_connect_org", fake_get_stripe_connect_org)
    monkeypatch.setattr(
        org_repo,
        "set_stripe_connect_account_id",
        fake_set_stripe_connect_account_id,
    )
    service = StripeConnectService(_db(), stripe_connect=cast("Any", stripe))

    response = await service.create_onboarding_link(
        org_id=org.org_id,
        user_id=uuid4(),
    )

    assert response.onboarding_url == "https://connect.stripe.com/setup/acct_existing"
    assert response.stripe_connect_account_id == "acct_existing"
    assert response.onboarding_required is False
    assert stripe.created_accounts == []
    assert stripe.account_links == ["acct_existing"]


async def test_onboarding_requires_owner_or_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stripe = FakeStripeConnect()

    async def fake_get_membership(
        _client: AsyncPostgrestClient, *, org_id: UUID, user_id: UUID
    ) -> OrgRole | None:
        return OrgRole.MEMBER

    async def fake_get_stripe_connect_org(
        _client: AsyncPostgrestClient, *, org_id: UUID
    ) -> StripeConnectOrgRecord | None:
        raise AssertionError("non-admin members should be rejected before org lookup")

    monkeypatch.setattr(org_repo, "get_membership", fake_get_membership)
    monkeypatch.setattr(org_repo, "get_stripe_connect_org", fake_get_stripe_connect_org)
    service = StripeConnectService(_db(), stripe_connect=cast("Any", stripe))

    with pytest.raises(ForbiddenError) as exc_info:
        await service.create_onboarding_link(org_id=uuid4(), user_id=uuid4())

    assert exc_info.value.code == "stripe_connect_forbidden"
    assert stripe.created_accounts == []
    assert stripe.account_links == []


async def test_stripe_account_link_payload_uses_settings_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_settings = Settings(
        SECRET_KEY="test-secret",
        DATABASE_URL="postgresql://example",
        SUPABASE_URL="https://supabase.test",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role",
        STRIPE_SECRET_KEY="sk_test_123",
        WEB_BASE_URL="https://app.example.com/",
    )
    client = StripeConnectClient(app_settings)
    calls: list[dict[str, Any]] = []

    async def fake_post(
        url: str,
        *,
        data: dict[str, str],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        calls.append({"url": url, "data": data, "idempotency_key": idempotency_key})
        return {"url": "https://connect.stripe.com/setup/acct_123"}

    monkeypatch.setattr(client, "_post", fake_post)

    result = await client.create_account_link(account_id="acct_123")

    assert result.url == "https://connect.stripe.com/setup/acct_123"
    assert calls == [
        {
            "url": STRIPE_ACCOUNT_LINKS_URL,
            "data": {
                "account": "acct_123",
                "type": "account_onboarding",
                "refresh_url": ("https://app.example.com/settings/billing/connect/refresh"),
                "return_url": ("https://app.example.com/settings/billing/connect/return"),
            },
            "idempotency_key": None,
        }
    ]


def test_connect_onboard_route_returns_minimal_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org_id = uuid4()
    user_id = uuid4()
    calls: list[dict[str, UUID]] = []

    class RouteStripeConnectService:
        def __init__(self, db: object, *, stripe_connect: object) -> None:
            self.db = db
            self.stripe_connect = stripe_connect

        async def create_onboarding_link(
            self,
            *,
            org_id: UUID,
            user_id: UUID,
        ) -> StripeConnectOnboardResponse:
            calls.append({"org_id": org_id, "user_id": user_id})
            return StripeConnectOnboardResponse(
                onboarding_url="https://connect.stripe.com/setup/acct_route",
                stripe_connect_account_id="acct_route",
                onboarding_required=True,
            )

    monkeypatch.setattr(
        stripe_connect_route,
        "StripeConnectService",
        RouteStripeConnectService,
    )

    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(stripe_connect_router, prefix="/api/v1")
    test_app.dependency_overrides[get_org_context] = lambda: UserContext(
        user_id=user_id,
        org_id=org_id,
    )
    test_app.dependency_overrides[get_user_scoped_db] = lambda: object()

    response = TestClient(test_app).post("/api/v1/stripe/connect/onboard")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "onboarding_url": "https://connect.stripe.com/setup/acct_route",
        "stripe_connect_account_id": "acct_route",
        "onboarding_required": True,
    }
    assert calls == [{"org_id": org_id, "user_id": user_id}]
