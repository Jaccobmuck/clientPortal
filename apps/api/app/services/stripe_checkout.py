from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from app.core.settings import Settings, settings
from app.exceptions import InternalError

if TYPE_CHECKING:
    from uuid import UUID

STRIPE_CHECKOUT_SESSIONS_URL = "https://api.stripe.com/v1/checkout/sessions"


@dataclass(frozen=True)
class StripeCheckoutResult:
    session_id: str
    checkout_url: str


class StripeCheckoutService:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def create_invoice_checkout_session(
        self,
        *,
        invoice_id: UUID,
        invoice_number: str,
        pay_token: UUID,
        org_id: UUID,
        connected_account_id: str,
        amount_due_cents: int,
        currency: str,
        client_email: str | None,
    ) -> StripeCheckoutResult:
        secret_key = self._require_secret_key()
        base_url = self._require_web_base_url()
        metadata = {
            "invoice_id": str(invoice_id),
            "invoice_number": invoice_number,
            "org_id": str(org_id),
            "pay_token": str(pay_token),
            "source": "freelio_pay_portal",
        }
        payload = self._build_payload(
            invoice_id=invoice_id,
            invoice_number=invoice_number,
            pay_token=pay_token,
            connected_account_id=connected_account_id,
            amount_due_cents=amount_due_cents,
            currency=currency,
            client_email=client_email,
            metadata=metadata,
            base_url=base_url,
        )
        headers = {
            "Authorization": f"Bearer {secret_key}",
            "Idempotency-Key": f"freelio-invoice-checkout-{invoice_id}-{amount_due_cents}",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    STRIPE_CHECKOUT_SESSIONS_URL,
                    headers=headers,
                    data=payload,
                )
        except httpx.HTTPError as exc:
            raise InternalError(
                "Stripe Checkout Session creation failed",
                code="stripe_checkout_failed",
            ) from exc

        if response.status_code >= 400:
            raise InternalError(
                "Stripe Checkout Session creation failed",
                code="stripe_checkout_failed",
            )

        data: Any = response.json()
        session_id = data.get("id") if isinstance(data, dict) else None
        checkout_url = data.get("url") if isinstance(data, dict) else None
        if not isinstance(session_id, str) or not isinstance(checkout_url, str):
            raise InternalError(
                "Stripe Checkout Session creation returned an unexpected response",
                code="stripe_checkout_unexpected",
            )
        return StripeCheckoutResult(session_id=session_id, checkout_url=checkout_url)

    def _require_secret_key(self) -> str:
        secret_key = self._settings.STRIPE_SECRET_KEY
        if secret_key is None or not secret_key.strip():
            raise InternalError("Stripe is not configured", code="stripe_not_configured")
        return secret_key

    def _require_web_base_url(self) -> str:
        web_base_url = self._settings.WEB_BASE_URL
        if web_base_url is None or not web_base_url.strip():
            raise InternalError(
                "WEB_BASE_URL is not configured", code="web_base_url_not_configured"
            )
        return web_base_url.rstrip("/")

    def _build_payload(
        self,
        *,
        invoice_id: UUID,
        invoice_number: str,
        pay_token: UUID,
        connected_account_id: str,
        amount_due_cents: int,
        currency: str,
        client_email: str | None,
        metadata: dict[str, str],
        base_url: str,
    ) -> dict[str, str]:
        payload = {
            "mode": "payment",
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][product_data][name]": f"Invoice {invoice_number}",
            "line_items[0][price_data][unit_amount]": str(amount_due_cents),
            "line_items[0][quantity]": "1",
            "payment_intent_data[transfer_data][destination]": connected_account_id,
            "client_reference_id": str(invoice_id),
            "success_url": (
                f"{base_url}/pay/{pay_token}/success?session_id={{CHECKOUT_SESSION_ID}}"
            ),
            "cancel_url": f"{base_url}/pay/{pay_token}",
        }
        platform_fee_cents = self._settings.STRIPE_PLATFORM_FEE_CENTS
        if platform_fee_cents > 0:
            payload["payment_intent_data[application_fee_amount]"] = str(platform_fee_cents)
        if client_email:
            payload["customer_email"] = client_email
        for key, value in metadata.items():
            payload[f"metadata[{key}]"] = value
            payload[f"payment_intent_data[metadata][{key}]"] = value
        return payload
