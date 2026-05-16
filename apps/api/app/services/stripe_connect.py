from uuid import UUID

from postgrest import AsyncPostgrestClient

from app.clients.stripe_connect import StripeConnectClient
from app.core.permissions import can_manage_payouts
from app.exceptions import ForbiddenError, NotFoundError
from app.repositories import org as org_repo
from app.schemas.stripe_connect import StripeConnectOnboardResponse


class StripeConnectService:
    def __init__(
        self,
        db: AsyncPostgrestClient,
        *,
        stripe_connect: StripeConnectClient,
    ) -> None:
        self._db = db
        self._stripe_connect = stripe_connect

    async def create_onboarding_link(
        self,
        *,
        org_id: UUID,
        user_id: UUID,
    ) -> StripeConnectOnboardResponse:
        role = await org_repo.get_membership(self._db, org_id=org_id, user_id=user_id)
        if role is None:
            raise NotFoundError("organization not found", code="org_not_found")
        if not can_manage_payouts(role):
            raise ForbiddenError(
                "you do not have permission to manage Stripe Connect",
                code="stripe_connect_forbidden",
            )

        org = await org_repo.get_stripe_connect_org(self._db, org_id=org_id)
        if org is None:
            raise NotFoundError("organization not found", code="org_not_found")

        account_id = org.stripe_connect_account_id
        if account_id is None or not account_id.strip():
            account = await self._stripe_connect.create_express_account(
                org_id=org.org_id,
                org_name=org.name,
            )
            org = await org_repo.set_stripe_connect_account_id(
                self._db,
                org_id=org.org_id,
                account_id=account.account_id,
            )
            account_id = account.account_id

        account_link = await self._stripe_connect.create_account_link(account_id=account_id)
        return StripeConnectOnboardResponse(
            onboarding_url=account_link.url,
            stripe_connect_account_id=account_id,
            onboarding_required=not org.stripe_connect_onboarding_complete,
        )
