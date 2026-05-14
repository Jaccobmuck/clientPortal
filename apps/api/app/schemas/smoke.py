from typing import Literal

from pydantic import BaseModel

from app.core.settings import ConfigPresence

SmokeActionName = Literal["queue", "email", "pdf", "reminder"]


class SmokeConfigStatus(BaseModel):
    enabled: bool
    all_required_present: bool
    required: list[ConfigPresence]


class SmokeActionStatus(BaseModel):
    action: SmokeActionName
    status: Literal["placeholder"]
    implemented: bool = False
    message: str
