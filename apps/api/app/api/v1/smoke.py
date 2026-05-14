from fastapi import APIRouter, HTTPException

from app.core.settings import settings
from app.schemas.base import BaseResponse
from app.schemas.smoke import SmokeActionName, SmokeActionStatus, SmokeConfigStatus

router = APIRouter(prefix="/smoke", tags=["smoke"])


def _require_smoke_tests_enabled() -> None:
    if not settings.ENABLE_SMOKE_TESTS:
        raise HTTPException(status_code=404, detail="Not found")


def _placeholder(action: SmokeActionName, message: str) -> BaseResponse[SmokeActionStatus]:
    _require_smoke_tests_enabled()
    return BaseResponse[SmokeActionStatus](
        success=True,
        data=SmokeActionStatus(
            action=action,
            status="placeholder",
            implemented=False,
            message=message,
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
        ),
    )


@router.post("/queue")
async def smoke_queue() -> BaseResponse[SmokeActionStatus]:
    return _placeholder(
        "queue",
        "Queue smoke action is a placeholder until worker processors are implemented.",
    )


@router.post("/email")
async def smoke_email() -> BaseResponse[SmokeActionStatus]:
    return _placeholder(
        "email",
        "Email smoke action is a placeholder and does not send email.",
    )


@router.post("/pdf")
async def smoke_pdf() -> BaseResponse[SmokeActionStatus]:
    return _placeholder(
        "pdf",
        "PDF smoke action is a placeholder and does not render or upload files.",
    )


@router.post("/reminder")
async def smoke_reminder() -> BaseResponse[SmokeActionStatus]:
    return _placeholder(
        "reminder",
        "Delayed reminder smoke action is a placeholder and does not enqueue jobs.",
    )
