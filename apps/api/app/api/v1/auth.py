from typing import Annotated

from fastapi import APIRouter, Depends
from supabase import AsyncClient

from app.core.deps import get_db
from app.schemas.auth import AuthTokenData, LoginRequest, RegisterRequest
from app.schemas.base import BaseResponse
from app.services.auth import login_user, register_user

router = APIRouter(tags=["auth"])

SupabaseDep = Annotated[AsyncClient, Depends(get_db)]


@router.post("/auth/register")
async def register(
    body: RegisterRequest,
    db: SupabaseDep,
) -> BaseResponse[AuthTokenData]:
    data = await register_user(
        db, email=body.email, password=body.password, full_name=body.full_name
    )
    return BaseResponse(success=True, data=data)


@router.post("/auth/login")
async def login(
    body: LoginRequest,
    db: SupabaseDep,
) -> BaseResponse[AuthTokenData]:
    data = await login_user(db, email=body.email, password=body.password)
    return BaseResponse(success=True, data=data)
