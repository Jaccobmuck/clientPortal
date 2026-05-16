from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import httpx

from app.core.settings import Settings, settings
from app.exceptions import InternalError

if TYPE_CHECKING:
    from uuid import UUID

STRIPE_ACCOUNTS_URL = "https://api.stripe.com/v1/accounts"
STRIPE_ACCOUNT_LINKS_URL = "https://api.stripe.com/v1/account_links"


@dataclass(frozen=True)
class StripeConnectAccount:
    account_id: str
    charges_enabled: bool
    payouts_enabled: bool
    details_submitted: bool


@dataclass(frozen=True)
class StripeAccountLink:
    url: str


class StripeConnectClient:
    def __init__(self, app_settings: Settings = settings) -> None:
        self._settings = app_settings

    async def create_express_account(
        self,
        *,
        org_id: UUID,
        org_name: str,
    ) -> StripeConnectAccount:
        data = await self._post(
            STRIPE_ACCOUNTS_URL,
            data={
                "type": "express",
                "business_profile[name]": org_name,
                "metadata[org_id]": str(org_id),
                "metadata[source]": "freelio_connect_onboarding",
                "capabilities[card_payments][requested]": "true",
                "capabilities[transfers][requested]": "true",
            },
            idempotency_key=f"freelio-connect-account-{org_id}",
        )
        return self._account_from_response(data)

    async def create_account_link(self, *, account_id: str) -> StripeAccountLink:
        data = await self._post(
            STRIPE_ACCOUNT_LINKS_URL,
            data={
                "account": account_id,
                "type": "account_onboarding",
                "refresh_url": self._connect_refresh_url(),
                "return_url": self._connect_return_url(),
            },
        )
        url = data.get("url")
        if not isinstance(url, str) or not url:
            raise InternalError(
                "Stripe account link returned an unexpected response",
                code="stripe_connect_account_link_unexpected",
            )
        return StripeAccountLink(url=url)

    async def retrieve_account(self, *, account_id: str) -> StripeConnectAccount:
        data = await self._get(f"{STRIPE_ACCOUNTS_URL}/{account_id}")
        return self._account_from_response(data)

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
                "Stripe Connect request failed", code="stripe_connect_failed"
            ) from exc

        return self._json_or_error(response)

    async def _get(self, url: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise InternalError(
                "Stripe Connect request failed", code="stripe_connect_failed"
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

    def _connect_refresh_url(self) -> str:
        return self._settings.STRIPE_CONNECT_REFRESH_URL or (
            f"{self._require_web_base_url()}/settings/billing/connect/refresh"
        )

    def _connect_return_url(self) -> str:
        return self._settings.STRIPE_CONNECT_RETURN_URL or (
            f"{self._require_web_base_url()}/settings/billing/connect/return"
        )

    def _require_web_base_url(self) -> str:
        web_base_url = self._settings.WEB_BASE_URL
        if web_base_url is None or not web_base_url.strip():
            raise InternalError(
                "WEB_BASE_URL is not configured", code="web_base_url_not_configured"
            )
        return web_base_url.rstrip("/")

    def _json_or_error(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise InternalError("Stripe Connect request failed", code="stripe_connect_failed")
        data: Any = response.json()
        if not isinstance(data, dict):
            raise InternalError(
                "Stripe Connect returned an unexpected response",
                code="stripe_connect_unexpected",
            )
        return data

    def _account_from_response(self, data: dict[str, Any]) -> StripeConnectAccount:
        account_id = data.get("id")
        if not isinstance(account_id, str) or not account_id:
            raise InternalError(
                "Stripe account returned an unexpected response",
                code="stripe_connect_account_unexpected",
            )
        return StripeConnectAccount(
            account_id=account_id,
            charges_enabled=bool(data.get("charges_enabled")),
            payouts_enabled=bool(data.get("payouts_enabled")),
            details_submitted=bool(data.get("details_submitted")),
        )
