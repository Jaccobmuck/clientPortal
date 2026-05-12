from uuid import UUID

from fastapi import APIRouter, Query

from app.core.deps import OrgUser, SupabaseDep
from app.exceptions import NotFoundError
from app.repositories import clients as repo
from app.schemas.base import BaseResponse
from app.schemas.clients import ClientResponse, CreateClientRequest, UpdateClientRequest

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/")
async def create_client(
    body: CreateClientRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ClientResponse]:
    data = body.model_dump()
    client = await repo.create_client(db, org_id=ctx.org_id, data=data)
    return BaseResponse(success=True, data=client)


@router.get("/")
async def list_clients(
    ctx: OrgUser,
    db: SupabaseDep,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> BaseResponse[list[ClientResponse]]:
    clamped_limit = min(limit, 100)
    clients = await repo.list_clients(
        db,
        org_id=ctx.org_id,
        search=search,
        limit=clamped_limit,
        offset=offset,
    )
    return BaseResponse(success=True, data=clients)


@router.get("/{client_id}")
async def get_client(
    client_id: UUID,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ClientResponse]:
    client = await repo.get_client(db, org_id=ctx.org_id, client_id=client_id)
    if client is None:
        raise NotFoundError("client not found", code="client_not_found")
    return BaseResponse(success=True, data=client)


@router.patch("/{client_id}")
async def update_client(
    client_id: UUID,
    body: UpdateClientRequest,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[ClientResponse]:
    fields = body.model_dump(exclude_unset=True)
    client = await repo.update_client(
        db,
        org_id=ctx.org_id,
        client_id=client_id,
        data=fields,
    )
    if client is None:
        raise NotFoundError("client not found", code="client_not_found")
    return BaseResponse(success=True, data=client)


@router.delete("/{client_id}")
async def delete_client(
    client_id: UUID,
    ctx: OrgUser,
    db: SupabaseDep,
) -> BaseResponse[None]:
    deleted = await repo.soft_delete_client(db, org_id=ctx.org_id, client_id=client_id)
    if not deleted:
        raise NotFoundError("client not found", code="client_not_found")
    return BaseResponse(success=True, data=None)
