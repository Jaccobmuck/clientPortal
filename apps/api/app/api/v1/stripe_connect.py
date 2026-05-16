from fastapi import APIRouter

from app.clients.stripe_connect import StripeConnectClient
from app.core.deps import OrgUser, SupabaseDep
from app.schemas.base import BaseResponse
from app.schemas.stripe_connect import StripeConnectOnboardResponse
from app.services.stripe_connect import StripeConnectService

router = APIRouter(prefix="/stripe", tags=["stripe-connect"])


@router.post("/connect/onboard")
async def create_connect_onboarding_link(
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[StripeConnectOnboardResponse]:
    service = StripeConnectService(db, stripe_connect=StripeConnectClient())
    onboarding = await service.create_onboarding_link(org_id=ctx.org_id, user_id=ctx.user_id)
    return BaseResponse(success=True, data=onboarding)
