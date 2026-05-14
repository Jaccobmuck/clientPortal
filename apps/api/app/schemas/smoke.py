from typing import Literal

from pydantic import BaseModel

from app.core.settings import ConfigPresence

SmokeActionName = Literal["queue", "email", "pdf", "reminder", "stripe"]
SmokeActionState = Literal["ok", "placeholder"]


class SmokeConfigStatus(BaseModel):
    enabled: bool
    all_required_present: bool
    required: list[ConfigPresence]
    smoke: list[ConfigPresence]


class SmokeNotificationStatus(BaseModel):
    provider: Literal["resend"]
    sent: bool
    recipient: str
    message_id: str | None = None


class SmokeActionStatus(BaseModel):
    action: SmokeActionName
    status: SmokeActionState
    implemented: bool = False
    message: str
    notification: SmokeNotificationStatus
