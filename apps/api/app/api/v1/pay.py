from typing import TYPE_CHECKING, cast

from fastapi import APIRouter, Depends
from supabase import AsyncClient

from app.core.deps import get_db
from app.schemas.base import BaseResponse
from app.schemas.pay import CheckoutSessionResponse, PublicInvoiceView
from app.services.pay_checkout import PayCheckoutService
from app.services.pay_portal import PayPortalService
from app.services.storage import PdfStorageService
from app.services.stripe_checkout import StripeCheckoutService

if TYPE_CHECKING:
    from postgrest import AsyncPostgrestClient

router = APIRouter(prefix="/pay", tags=["pay"])

_depends_supabase = Depends(get_db)


@router.get("/{token}")
async def get_public_invoice(
    token: str,
    supabase: AsyncClient = _depends_supabase,
) -> BaseResponse[PublicInvoiceView]:
    service = PayPortalService(
        cast("AsyncPostgrestClient", supabase),
        pdf_storage=PdfStorageService(supabase),
    )
    invoice = await service.get_public_invoice_view(raw_token=token)
    return BaseResponse(success=True, data=invoice)


@router.post("/{token}/checkout")
async def create_public_invoice_checkout(
    token: str,
    supabase: AsyncClient = _depends_supabase,
) -> BaseResponse[CheckoutSessionResponse]:
    service = PayCheckoutService(
        cast("AsyncPostgrestClient", supabase),
        stripe_checkout=StripeCheckoutService(),
    )
    checkout = await service.create_checkout_session(raw_token=token)
    return BaseResponse(success=True, data=checkout)
