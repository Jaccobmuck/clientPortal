from fastapi import APIRouter

from app.clients.stripe_billing import StripeBillingClient
from app.core.deps import CurrentUser, SupabaseDep
from app.schemas.base import BaseResponse
from app.schemas.billing import BillingCheckoutResponse, BillingPortalResponse
from app.services.billing import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/subscribe")
async def create_billing_subscription_checkout(
    user: CurrentUser,
    db: SupabaseDep,
) -> BaseResponse[BillingCheckoutResponse]:
    service = BillingService(db, stripe_billing=StripeBillingClient())
    checkout = await service.create_subscription_checkout(
        user_id=user.user_id,
        user_email=user.email,
    )
    return BaseResponse(success=True, data=checkout)


@router.post("/portal")
async def create_billing_portal_session(
    user: CurrentUser,
    db: SupabaseDep,
) -> BaseResponse[BillingPortalResponse]:
    service = BillingService(db, stripe_billing=StripeBillingClient())
    portal = await service.create_billing_portal(user_id=user.user_id)
    return BaseResponse(success=True, data=portal)
