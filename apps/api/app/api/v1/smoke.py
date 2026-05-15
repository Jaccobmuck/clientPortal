from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.schemas.base import BaseResponse
from app.schemas.smoke import (
    SmokeActionName,
    SmokeActionState,
    SmokeActionStatus,
    SmokeConfigStatus,
)
from app.services.smoke import (
    check_stripe_credentials,
    create_stripe_test_transaction,
    send_smoke_notification,
)

router = APIRouter(prefix="/smoke", tags=["smoke"])


def _require_smoke_tests_enabled() -> None:
    if not settings.ENABLE_SMOKE_TESTS:
        raise HTTPException(status_code=404, detail="Not found")


async def _action_response(
    *,
    action: SmokeActionName,
    state: SmokeActionState,
    implemented: bool,
    message: str,
) -> BaseResponse[SmokeActionStatus]:
    _require_smoke_tests_enabled()
    notification = await send_smoke_notification(action=action, status_message=message)
    return BaseResponse[SmokeActionStatus](
        success=True,
        data=SmokeActionStatus(
            action=action,
            status=state,
            implemented=implemented,
            message=message,
            notification=notification,
        ),
    )


@router.get("/config")
async def get_smoke_config() -> BaseResponse[SmokeConfigStatus]:
    _require_smoke_tests_enabled()
    return BaseResponse[SmokeConfigStatus](
        success=True,
        data=SmokeConfigStatus(
            enabled=settings.ENABLE_SMOKE_TESTS,
            all_required_present=settings.required_config_ready(),
            required=settings.required_config_presence(),
            smoke=settings.smoke_config_presence(),
        ),
    )


@router.post("/queue")
async def smoke_queue() -> BaseResponse[SmokeActionStatus]:
    return await _action_response(
        action="queue",
        state="placeholder",
        implemented=False,
        message="Queue smoke action is a placeholder until worker processors are implemented.",
    )


@router.post("/email")
async def smoke_email() -> BaseResponse[SmokeActionStatus]:
    return await _action_response(
        action="email",
        state="ok",
        implemented=True,
        message="Resend smoke email was accepted by the provider.",
    )


@router.post("/pdf")
async def smoke_pdf() -> BaseResponse[SmokeActionStatus]:
    from app.pdf.smoke import smoke_render_pdf

    pdf_bytes, _filename = smoke_render_pdf()
    file_size_kb = len(pdf_bytes) / 1024

    return await _action_response(
        action="pdf",
        state="ok",
        implemented=True,
        message=f"PDF rendered successfully ({file_size_kb:.1f} KB). WeasyPrint and Jinja2 template are operational.",
    )


@router.post("/reminder")
async def smoke_reminder() -> BaseResponse[SmokeActionStatus]:
    return await _action_response(
        action="reminder",
        state="placeholder",
        implemented=False,
        message="Delayed reminder smoke action is a placeholder and does not enqueue jobs.",
    )


@router.post("/stripe")
async def smoke_stripe() -> BaseResponse[SmokeActionStatus]:
    _require_smoke_tests_enabled()
    await check_stripe_credentials()
    return await _action_response(
        action="stripe",
        state="ok",
        implemented=True,
        message="Stripe test API credentials responded successfully; no payment objects were created.",
    )


@router.post("/stripe/transaction")
async def smoke_stripe_transaction() -> BaseResponse[SmokeActionStatus]:
    _require_smoke_tests_enabled()
    payment_intent_id = await create_stripe_test_transaction()
    message = f"Stripe test PaymentIntent succeeded in test mode with id {payment_intent_id}."
    return await _action_response(
        action="stripe_transaction",
        state="ok",
        implemented=True,
        message=message,
    )
