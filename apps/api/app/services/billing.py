from __future__ import annotations

from typing import TYPE_CHECKING

from app.exceptions import ConflictError, NotFoundError
from app.repositories import billing as billing_repo
from app.schemas.billing import BillingCheckoutResponse, BillingPortalResponse

if TYPE_CHECKING:
    from uuid import UUID

    from postgrest import AsyncPostgrestClient

    from app.clients.stripe_billing import StripeBillingClient
    from app.repositories.billing import BillingAccountRecord

_TERMINAL_SUBSCRIPTION_STATUSES = frozenset({"free", "canceled", "incomplete_expired"})


def calculate_billable_org_count(total_org_count: int) -> int:
    return max(total_org_count - 1, 0)


def _has_active_or_pending_subscription(account: BillingAccountRecord) -> bool:
    if not account.stripe_subscription_id:
        return False
    return account.billing_status not in _TERMINAL_SUBSCRIPTION_STATUSES


class BillingService:
    def __init__(
        self,
        db: AsyncPostgrestClient,
        *,
        stripe_billing: StripeBillingClient,
    ) -> None:
        self._db = db
        self._stripe_billing = stripe_billing

    async def create_subscription_checkout(
        self,
        *,
        user_id: UUID,
        user_email: str | None,
    ) -> BillingCheckoutResponse:
        account = await self._get_billing_account(user_id=user_id)
        total_org_count = await billing_repo.count_owned_organizations(
            self._db,
            user_id=user_id,
        )
        billable_org_count = calculate_billable_org_count(total_org_count)
        if billable_org_count == 0:
            raise ConflictError(
                "no paid subscription is required for this account",
                code="billing_not_required",
            )
        if _has_active_or_pending_subscription(account):
            raise ConflictError(
                "billing subscription already exists; use the billing portal",
                code="billing_subscription_exists",
            )

        customer_id = account.stripe_customer_id.strip() if account.stripe_customer_id else None
        if customer_id is None:
            customer = await self._stripe_billing.create_customer(
                user_id=user_id,
                email=user_email or account.email,
            )
            await billing_repo.set_stripe_customer_id(
                self._db,
                user_id=user_id,
                customer_id=customer.customer_id,
            )
            customer_id = customer.customer_id

        checkout = await self._stripe_billing.create_subscription_checkout_session(
            customer_id=customer_id,
            user_id=user_id,
            billable_org_count=billable_org_count,
        )
        return BillingCheckoutResponse(checkout_url=checkout.checkout_url)

    async def create_billing_portal(
        self,
        *,
        user_id: UUID,
    ) -> BillingPortalResponse:
        account = await billing_repo.get_billing_account(self._db, user_id=user_id)
        customer_id = (
            account.stripe_customer_id.strip() if account and account.stripe_customer_id else None
        )
        subscription_id = (
            account.stripe_subscription_id.strip()
            if account and account.stripe_subscription_id
            else None
        )
        if account is None or not customer_id or not subscription_id:
            raise ConflictError(
                "billing is not initialized for this account",
                code="billing_not_initialized",
            )

        portal = await self._stripe_billing.create_billing_portal_session(
            customer_id=customer_id,
        )
        return BillingPortalResponse(portal_url=portal.portal_url)

    async def _get_billing_account(self, *, user_id: UUID) -> BillingAccountRecord:
        account = await billing_repo.get_billing_account(self._db, user_id=user_id)
        if account is None:
            raise NotFoundError(
                "billing account not found",
                code="billing_account_not_found",
            )
        return account
