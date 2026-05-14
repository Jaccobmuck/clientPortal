from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx

from app.core.settings import settings
from app.exceptions import InternalError, ValidationError
from app.schemas.smoke import SmokeActionName, SmokeNotificationStatus

RESEND_EMAIL_URL = "https://api.resend.com/emails"
STRIPE_BALANCE_URL = "https://api.stripe.com/v1/balance"
STRIPE_PAYMENT_INTENTS_URL = "https://api.stripe.com/v1/payment_intents"


def _require_setting(name: str, value: str | None, *, code: str) -> str:
    if value is None or not value.strip():
        raise ValidationError(f"{name} is not configured", code=code)
    return value


def _require_stripe_test_secret_key() -> str:
    secret_key = _require_setting(
        "STRIPE_SECRET_KEY",
        settings.STRIPE_SECRET_KEY,
        code="stripe_not_configured",
    )
    if not secret_key.startswith("sk_test_"):
        raise ValidationError(
            "Stripe smoke checks require a Stripe test secret key",
            code="stripe_live_key_rejected",
        )
    return secret_key


async def send_smoke_notification(
    *,
    action: SmokeActionName,
    status_message: str,
) -> SmokeNotificationStatus:
    api_key = _require_setting(
        "RESEND_API_KEY",
        settings.RESEND_API_KEY,
        code="resend_not_configured",
    )
    from_email = _require_setting(
        "RESEND_FROM_EMAIL",
        settings.RESEND_FROM_EMAIL,
        code="resend_not_configured",
    )
    recipient = _require_setting(
        "SMOKE_TEST_EMAIL",
        settings.SMOKE_TEST_EMAIL,
        code="smoke_email_not_configured",
    )

    result_line = f"Result: {status_message}"
    text = f"The Freelio smoke endpoint '{action}' returned OK.\n\n{result_line}"

    payload = {
        "from": from_email,
        "to": [recipient],
        "subject": f"Freelio smoke OK: {action}",
        "text": text,
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(RESEND_EMAIL_URL, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise InternalError("Resend smoke email failed", code="resend_email_failed") from exc

    if response.status_code >= 400:
        raise InternalError("Resend smoke email failed", code="resend_email_failed")

    data = response.json()
    message_id = data.get("id") if isinstance(data, dict) else None
    return SmokeNotificationStatus(
        provider="resend",
        sent=True,
        recipient=recipient,
        message_id=str(message_id) if message_id else None,
    )


async def check_stripe_credentials() -> None:
    secret_key = _require_stripe_test_secret_key()

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                STRIPE_BALANCE_URL,
                headers={"Authorization": f"Bearer {secret_key}"},
            )
    except httpx.HTTPError as exc:
        raise InternalError("Stripe smoke check failed", code="stripe_smoke_failed") from exc

    if response.status_code >= 400:
        raise InternalError("Stripe smoke check failed", code="stripe_smoke_failed")

    data: Any = response.json()
    if not isinstance(data, dict) or "object" not in data:
        raise InternalError("Stripe smoke check returned an unexpected response")


async def create_stripe_test_transaction() -> str:
    if not settings.ENABLE_STRIPE_SMOKE_TRANSACTIONS:
        raise ValidationError(
            "Stripe smoke test transactions are disabled",
            code="stripe_smoke_transactions_disabled",
        )

    secret_key = _require_stripe_test_secret_key()
    headers = {
        "Authorization": f"Bearer {secret_key}",
        "Idempotency-Key": f"freelio-smoke-{uuid4()}",
    }
    payload = {
        "amount": "100",
        "currency": "usd",
        "payment_method": "pm_card_visa",
        "payment_method_types[]": "card",
        "confirm": "true",
        "metadata[smoke_test]": "true",
        "metadata[environment]": settings.ENVIRONMENT,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                STRIPE_PAYMENT_INTENTS_URL,
                headers=headers,
                data=payload,
            )
    except httpx.HTTPError as exc:
        raise InternalError(
            "Stripe smoke test transaction failed",
            code="stripe_smoke_transaction_failed",
        ) from exc

    if response.status_code >= 400:
        raise InternalError(
            "Stripe smoke test transaction failed",
            code="stripe_smoke_transaction_failed",
        )

    data: Any = response.json()
    if (
        not isinstance(data, dict)
        or data.get("object") != "payment_intent"
        or data.get("status") != "succeeded"
        or not data.get("id")
    ):
        raise InternalError(
            "Stripe smoke test transaction returned an unexpected response",
            code="stripe_smoke_transaction_unexpected",
        )

    return str(data["id"])
