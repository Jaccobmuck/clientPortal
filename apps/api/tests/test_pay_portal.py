from __future__ import annotations

import os
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DATABASE_URL", "postgresql://example")
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")

from app.api.v1 import pay as pay_route
from app.api.v1.pay import router as pay_router
from app.core.deps import get_db
from app.core.settings import Settings
from app.exceptions import ConflictError, NotFoundError
from app.middleware.exception_handlers import register_exception_handlers
from app.repositories import invoices as invoice_repo
from app.repositories.invoices import PublicInvoiceLineItemRecord, PublicInvoiceRecord
from app.schemas.invoices import InvoiceStatus
from app.services.pay_checkout import PayCheckoutService
from app.services.pay_portal import PayPortalService
from app.services.stripe_checkout import StripeCheckoutResult, StripeCheckoutService

if TYPE_CHECKING:
    from postgrest import AsyncPostgrestClient

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakePdfStorage:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.paths: list[str] = []

    async def create_signed_invoice_pdf_url(self, storage_path: str) -> str:
        self.paths.append(storage_path)
        if self.fail:
            raise RuntimeError("storage unavailable")
        return f"https://storage.test/{storage_path}?signed=1"


class FakeStripeCheckout:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create_invoice_checkout_session(self, **kwargs: Any) -> StripeCheckoutResult:
        self.calls.append(kwargs)
        return StripeCheckoutResult(
            session_id="cs_test_123",
            checkout_url="https://checkout.stripe.com/pay/cs_test_123",
        )


def _db() -> AsyncPostgrestClient:
    return cast("AsyncPostgrestClient", object())


def _record(**overrides: Any) -> PublicInvoiceRecord:
    total = overrides.pop("total_cents", 12000)
    paid = overrides.pop("amount_paid_cents", 0)
    values = {
        "invoice_id": uuid4(),
        "org_id": uuid4(),
        "pay_token": uuid4(),
        "status": InvoiceStatus.SENT.value,
        "invoice_number": "INV-0007",
        "issued_at": datetime(2026, 5, 13, tzinfo=UTC),
        "due_at": date(2026, 5, 30),
        "paid_at": None,
        "voided_at": None,
        "is_public_viewable": True,
        "subtotal_cents": 10000,
        "tax_cents": 2000,
        "discount_cents": 0,
        "total_cents": total,
        "amount_paid_cents": paid,
        "amount_due_cents": max(total - paid, 0),
        "currency": "usd",
        "org_name": "Freelio Studio",
        "org_logo_url": "https://cdn.test/logo.png",
        "org_brand_color": "#102030",
        "org_support_email": "support@example.com",
        "stripe_account_id": "acct_123",
        "stripe_payments_enabled": True,
        "client_name": "Acme Co",
        "client_email": "ap@example.com",
        "line_items": [
            PublicInvoiceLineItemRecord(
                description="Consulting",
                quantity="1",
                unit_amount_cents=10000,
                line_total_cents=10000,
            )
        ],
        "pdf_storage_path": None,
    }
    values.update(overrides)
    return PublicInvoiceRecord(**values)


async def _stub_invoice(
    monkeypatch: pytest.MonkeyPatch, record: PublicInvoiceRecord | None
) -> None:
    async def fake_get_public_invoice_by_pay_token(
        _client: AsyncPostgrestClient, *, token: UUID
    ) -> PublicInvoiceRecord | None:
        return record

    monkeypatch.setattr(
        invoice_repo,
        "get_public_invoice_by_pay_token",
        fake_get_public_invoice_by_pay_token,
    )


async def test_unknown_token_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    await _stub_invoice(monkeypatch, None)
    service = PayPortalService(_db(), pdf_storage=cast("Any", FakePdfStorage()))

    with pytest.raises(NotFoundError) as exc_info:
        await service.get_public_invoice_view(raw_token=str(uuid4()))

    assert exc_info.value.message == "Invoice not found"


async def test_draft_invoice_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    await _stub_invoice(
        monkeypatch,
        _record(status=InvoiceStatus.DRAFT.value, is_public_viewable=False),
    )
    service = PayPortalService(_db(), pdf_storage=cast("Any", FakePdfStorage()))

    with pytest.raises(NotFoundError):
        await service.get_public_invoice_view(raw_token=str(uuid4()))


async def test_sent_invoice_returns_public_invoice_view(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = FakePdfStorage()
    await _stub_invoice(monkeypatch, _record(pdf_storage_path="invoices/inv.pdf"))
    service = PayPortalService(_db(), pdf_storage=cast("Any", storage))

    view = await service.get_public_invoice_view(raw_token=str(uuid4()))

    assert view.invoice_number == "INV-0007"
    assert view.org.name == "Freelio Studio"
    assert view.client.email == "ap@example.com"
    assert view.line_items[0].description == "Consulting"
    assert view.is_payable is True
    assert view.pdf_url == "https://storage.test/invoices/inv.pdf?signed=1"


async def test_paid_invoice_is_visible_but_not_payable(monkeypatch: pytest.MonkeyPatch) -> None:
    await _stub_invoice(
        monkeypatch,
        _record(
            status=InvoiceStatus.PAID.value,
            paid_at=datetime(2026, 5, 14, tzinfo=UTC),
            amount_paid_cents=12000,
        ),
    )
    service = PayPortalService(_db(), pdf_storage=cast("Any", FakePdfStorage()))

    view = await service.get_public_invoice_view(raw_token=str(uuid4()))

    assert view.is_payable is False
    assert view.not_payable_reason == "already_paid"


async def test_invoice_with_no_pdf_returns_null_pdf_url(monkeypatch: pytest.MonkeyPatch) -> None:
    storage = FakePdfStorage()
    await _stub_invoice(monkeypatch, _record(pdf_storage_path=None))
    service = PayPortalService(_db(), pdf_storage=cast("Any", storage))

    view = await service.get_public_invoice_view(raw_token=str(uuid4()))

    assert view.pdf_url is None
    assert storage.paths == []


async def test_pdf_signing_failure_returns_null_pdf_url(monkeypatch: pytest.MonkeyPatch) -> None:
    await _stub_invoice(monkeypatch, _record(pdf_storage_path="invoices/inv.pdf"))
    service = PayPortalService(_db(), pdf_storage=cast("Any", FakePdfStorage(fail=True)))

    view = await service.get_public_invoice_view(raw_token=str(uuid4()))

    assert view.pdf_url is None


async def test_public_response_excludes_private_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    await _stub_invoice(monkeypatch, _record())
    service = PayPortalService(_db(), pdf_storage=cast("Any", FakePdfStorage()))

    payload = (await service.get_public_invoice_view(raw_token=str(uuid4()))).model_dump(
        mode="json"
    )

    hidden = {"org_id", "client_id", "owner_id", "stripe_account_id", "metadata", "notes"}
    assert hidden.isdisjoint(payload)
    assert hidden.isdisjoint(payload["org"])
    assert hidden.isdisjoint(payload["client"])


async def test_checkout_unknown_token_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    stripe = FakeStripeCheckout()
    await _stub_invoice(monkeypatch, None)
    service = PayCheckoutService(_db(), stripe_checkout=cast("Any", stripe))

    with pytest.raises(NotFoundError):
        await service.create_checkout_session(raw_token=str(uuid4()))

    assert stripe.calls == []


async def test_checkout_draft_invoice_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    stripe = FakeStripeCheckout()
    await _stub_invoice(
        monkeypatch,
        _record(status=InvoiceStatus.DRAFT.value, is_public_viewable=False),
    )
    service = PayCheckoutService(_db(), stripe_checkout=cast("Any", stripe))

    with pytest.raises(NotFoundError):
        await service.create_checkout_session(raw_token=str(uuid4()))

    assert stripe.calls == []


@pytest.mark.parametrize(
    ("record", "error_code"),
    [
        (
            _record(
                status=InvoiceStatus.PAID.value,
                paid_at=datetime(2026, 5, 14, tzinfo=UTC),
                amount_paid_cents=12000,
            ),
            "invoice_already_paid",
        ),
        (_record(total_cents=0), "invoice_no_amount_due"),
        (_record(stripe_account_id=None), "invoice_payments_unavailable"),
    ],
)
async def test_checkout_rejects_not_payable_invoices(
    monkeypatch: pytest.MonkeyPatch,
    record: PublicInvoiceRecord,
    error_code: str,
) -> None:
    stripe = FakeStripeCheckout()
    await _stub_invoice(monkeypatch, record)
    service = PayCheckoutService(_db(), stripe_checkout=cast("Any", stripe))

    with pytest.raises(ConflictError) as exc_info:
        await service.create_checkout_session(raw_token=str(uuid4()))

    assert exc_info.value.code == error_code
    assert stripe.calls == []


async def test_checkout_payable_invoice_uses_server_derived_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stripe = FakeStripeCheckout()
    record = _record(
        total_cents=12000,
        amount_paid_cents=2500,
        currency="eur",
        stripe_account_id=" acct_connected ",
        client_email="billing@example.com",
    )
    await _stub_invoice(monkeypatch, record)
    service = PayCheckoutService(_db(), stripe_checkout=cast("Any", stripe))

    response = await service.create_checkout_session(raw_token=str(record.pay_token))

    assert response.checkout_url == "https://checkout.stripe.com/pay/cs_test_123"
    assert stripe.calls == [
        {
            "invoice_id": record.invoice_id,
            "invoice_number": "INV-0007",
            "pay_token": record.pay_token,
            "org_id": record.org_id,
            "connected_account_id": "acct_connected",
            "amount_due_cents": 9500,
            "currency": "eur",
            "client_email": "billing@example.com",
        }
    ]


def test_invalid_token_checkout_route_returns_404() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(pay_router, prefix="/api/v1")
    test_app.dependency_overrides[get_db] = lambda: object()

    response = TestClient(test_app).post("/api/v1/pay/not-a-token/checkout")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Invoice not found"


def test_checkout_route_ignores_client_supplied_payment_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_stripe_services: list[FakeStripeCheckout] = []

    class RouteStripeCheckout(FakeStripeCheckout):
        def __init__(self) -> None:
            super().__init__()
            created_stripe_services.append(self)

    record = _record()

    async def fake_get_public_invoice_by_pay_token(
        _client: AsyncPostgrestClient, *, token: UUID
    ) -> PublicInvoiceRecord:
        return record

    monkeypatch.setattr(
        invoice_repo,
        "get_public_invoice_by_pay_token",
        fake_get_public_invoice_by_pay_token,
    )
    monkeypatch.setattr(pay_route, "StripeCheckoutService", RouteStripeCheckout)

    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(pay_router, prefix="/api/v1")
    test_app.dependency_overrides[get_db] = lambda: object()

    response = TestClient(test_app).post(
        f"/api/v1/pay/{record.pay_token}/checkout",
        json={
            "amount_due_cents": 1,
            "currency": "jpy",
            "connected_account_id": "acct_attacker",
            "invoice_id": str(uuid4()),
        },
    )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "session_id": "cs_test_123",
        "checkout_url": "https://checkout.stripe.com/pay/cs_test_123",
    }
    assert created_stripe_services[0].calls[0]["amount_due_cents"] == record.amount_due_cents
    assert created_stripe_services[0].calls[0]["currency"] == record.currency
    assert created_stripe_services[0].calls[0]["connected_account_id"] == record.stripe_account_id


def test_stripe_checkout_payload_includes_connect_metadata_and_urls() -> None:
    app_settings = Settings(
        SECRET_KEY="test-secret",
        DATABASE_URL="postgresql://example",
        SUPABASE_URL="https://supabase.test",
        SUPABASE_SERVICE_ROLE_KEY="test-service-role",
        STRIPE_SECRET_KEY="sk_test_123",
        STRIPE_PLATFORM_FEE_CENTS=250,
        WEB_BASE_URL="https://pay.example.com",
    )
    service = StripeCheckoutService(app_settings)
    invoice_id = uuid4()
    pay_token = uuid4()
    org_id = uuid4()
    metadata = {
        "invoice_id": str(invoice_id),
        "invoice_number": "INV-0007",
        "org_id": str(org_id),
        "pay_token": str(pay_token),
        "source": "freelio_pay_portal",
    }

    payload = service._build_payload(
        invoice_id=invoice_id,
        invoice_number="INV-0007",
        pay_token=pay_token,
        connected_account_id="acct_connected",
        amount_due_cents=9500,
        currency="usd",
        client_email="billing@example.com",
        metadata=metadata,
        base_url="https://pay.example.com",
    )

    assert payload["payment_intent_data[transfer_data][destination]"] == "acct_connected"
    assert payload["payment_intent_data[application_fee_amount]"] == "250"
    assert payload["client_reference_id"] == str(invoice_id)
    assert payload["customer_email"] == "billing@example.com"
    assert payload["success_url"] == (
        f"https://pay.example.com/pay/{pay_token}/success?session_id={{CHECKOUT_SESSION_ID}}"
    )
    assert payload["cancel_url"] == f"https://pay.example.com/pay/{pay_token}"
    for key, value in metadata.items():
        assert payload[f"metadata[{key}]"] == value
        assert payload[f"payment_intent_data[metadata][{key}]"] == value


def test_invalid_token_route_returns_404() -> None:
    test_app = FastAPI()
    register_exception_handlers(test_app)
    test_app.include_router(pay_router, prefix="/api/v1")
    test_app.dependency_overrides[get_db] = lambda: object()

    response = TestClient(test_app).get("/api/v1/pay/not-a-token")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Invoice not found"
