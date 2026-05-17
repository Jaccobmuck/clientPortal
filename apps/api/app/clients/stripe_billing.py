from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from app.core.settings import Settings, settings
from app.exceptions import BadRequestError, InternalError

if TYPE_CHECKING:
    from uuid import UUID

STRIPE_CUSTOMERS_URL = "https://api.stripe.com/v1/customers"
STRIPE_CHECKOUT_SESSIONS_URL = "https://api.stripe.com/v1/checkout/sessions"
STRIPE_BILLING_PORTAL_SESSIONS_URL = "https://api.stripe.com/v1/billing_portal/sessions"
STRIPE_SUBSCRIPTIONS_URL = "https://api.stripe.com/v1/subscriptions"


@dataclass(frozen=True)
class StripeBillingCustomer:
    customer_id: str


@dataclass(frozen=True)
class StripeBillingCheckoutSession:
    session_id: str
    checkout_url: str


@dataclass(frozen=True)
class StripeBillingPortalSession:
    portal_url: str


@dataclass(frozen=True)
class StripeBillingSubscription:
    subscription_id: str
    status: str | None
    current_period_end: int | None


class StripeBillingClient:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def create_customer(
        self,
        *,
        user_id: UUID,
        email: str | None,
    ) -> StripeBillingCustomer:
        payload = {
            "metadata[user_id]": str(user_id),
            "metadata[source]": "freelio_saas_billing",
        }
        if email:
            payload["email"] = email

        data = await self._post(
            STRIPE_CUSTOMERS_URL,
            data=payload,
            idempotency_key=f"freelio-billing-customer-{user_id}",
        )
        customer_id = data.get("id")
        if not isinstance(customer_id, str) or not customer_id:
            raise InternalError(
                "Stripe customer returned an unexpected response",
                code="stripe_customer_unexpected",
            )
        return StripeBillingCustomer(customer_id=customer_id)

    async def create_subscription_checkout_session(
        self,
        *,
        customer_id: str,
        user_id: UUID,
        billable_org_count: int,
    ) -> StripeBillingCheckoutSession:
        payload = self._build_subscription_checkout_payload(
            customer_id=customer_id,
            user_id=user_id,
            billable_org_count=billable_org_count,
            base_url=self._require_web_base_url(),
            additional_org_price_id=self._require_additional_org_price_id(),
            base_price_id=self._optional_base_price_id(),
        )
        data = await self._post(
            STRIPE_CHECKOUT_SESSIONS_URL,
            data=payload,
            idempotency_key=f"freelio-billing-checkout-{user_id}-{billable_org_count}",
        )
        session_id = data.get("id")
        checkout_url = data.get("url")
        if not isinstance(session_id, str) or not isinstance(checkout_url, str):
            raise InternalError(
                "Stripe billing Checkout Session returned an unexpected response",
                code="stripe_billing_checkout_unexpected",
            )
        return StripeBillingCheckoutSession(
            session_id=session_id,
            checkout_url=checkout_url,
        )

    async def create_billing_portal_session(
        self,
        *,
        customer_id: str,
    ) -> StripeBillingPortalSession:
        data = await self._post(
            STRIPE_BILLING_PORTAL_SESSIONS_URL,
            data={
                "customer": customer_id,
                "return_url": f"{self._require_web_base_url()}/settings/billing",
            },
        )
        portal_url = data.get("url")
        if not isinstance(portal_url, str) or not portal_url:
            raise InternalError(
                "Stripe billing portal returned an unexpected response",
                code="stripe_billing_portal_unexpected",
            )
        return StripeBillingPortalSession(portal_url=portal_url)

    async def retrieve_subscription(
        self,
        *,
        subscription_id: str,
    ) -> StripeBillingSubscription:
        data = await self._get(f"{STRIPE_SUBSCRIPTIONS_URL}/{subscription_id}")
        retrieved_id = data.get("id")
        if not isinstance(retrieved_id, str) or not retrieved_id:
            raise InternalError(
                "Stripe subscription returned an unexpected response",
                code="stripe_subscription_unexpected",
            )
        current_period_end = data.get("current_period_end")
        if not isinstance(current_period_end, int):
            current_period_end = None
        status = data.get("status")
        return StripeBillingSubscription(
            subscription_id=retrieved_id,
            status=status if isinstance(status, str) else None,
            current_period_end=current_period_end,
        )

    def _build_subscription_checkout_payload(
        self,
        *,
        customer_id: str,
        user_id: UUID,
        billable_org_count: int,
        base_url: str,
        additional_org_price_id: str,
        base_price_id: str | None,
    ) -> dict[str, str]:
        payload = {
            "mode": "subscription",
            "customer": customer_id,
            "client_reference_id": str(user_id),
            "success_url": (
                f"{base_url}/settings/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
            ),
            "cancel_url": f"{base_url}/settings/billing",
            "metadata[user_id]": str(user_id),
            "metadata[source]": "freelio_saas_billing",
            "metadata[billable_org_count]": str(billable_org_count),
            "subscription_data[metadata][user_id]": str(user_id),
            "subscription_data[metadata][source]": "freelio_saas_billing",
            "subscription_data[metadata][billable_org_count]": str(billable_org_count),
        }

        line_index = 0
        if base_price_id:
            payload[f"line_items[{line_index}][price]"] = base_price_id
            payload[f"line_items[{line_index}][quantity]"] = "1"
            line_index += 1

        for _ in range(billable_org_count):
            payload[f"line_items[{line_index}][price]"] = additional_org_price_id
            payload[f"line_items[{line_index}][quantity]"] = "1"
            line_index += 1

        return payload

    async def _post(
        self,
        url: str,
        *,
        data: dict[str, str],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = self._headers(idempotency_key=idempotency_key)
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(url, headers=headers, data=data)
        except httpx.HTTPError as exc:
            raise InternalError(
                "Stripe Billing request failed", code="stripe_billing_failed"
            ) from exc

        return self._json_or_error(response)

    async def _get(self, url: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise InternalError(
                "Stripe Billing request failed", code="stripe_billing_failed"
            ) from exc

        return self._json_or_error(response)

    def _headers(self, *, idempotency_key: str | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self._require_secret_key()}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

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

    def _require_additional_org_price_id(self) -> str:
        price_id = self._settings.STRIPE_BILLING_ADDITIONAL_ORG_PRICE_ID
        if price_id is None or not price_id.strip():
            raise BadRequestError(
                "Stripe billing price is not configured",
                code="billing_price_not_configured",
            )
        return price_id

    def _optional_base_price_id(self) -> str | None:
        price_id = self._settings.STRIPE_BILLING_BASE_PRICE_ID
        return price_id.strip() if price_id and price_id.strip() else None

    def _json_or_error(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise InternalError("Stripe Billing request failed", code="stripe_billing_failed")
        data: Any = response.json()
        if not isinstance(data, dict):
            raise InternalError(
                "Stripe Billing returned an unexpected response",
                code="stripe_billing_unexpected",
            )
        return data
