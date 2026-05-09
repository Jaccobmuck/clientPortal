"""Free-tier guard for organization creation.

Counts orgs the caller *owns*. Memberships where the caller is admin or
member do not count toward the inviter's limit, only OWNER memberships do.
This is the entire scope of this module — no Stripe, no subscriptions
table, no billing state.
"""

from typing import Any, cast

from fastapi import Depends
from postgrest import AsyncPostgrestClient
from postgrest.exceptions import APIError

from app.core.deps import get_current_user, get_user_scoped_db
from app.core.permissions import OrgRole
from app.core.settings import settings
from app.exceptions import InternalError, SubscriptionRequiredError
from app.schemas.auth import AuthUser

_depends_current_user = Depends(get_current_user)
_depends_db = Depends(get_user_scoped_db)


async def require_org_creation_allowed(
    current_user: AuthUser = _depends_current_user,
    db: AsyncPostgrestClient = _depends_db,
) -> None:
    try:
        response = (
            await db.from_("organization_members")
            .select("org_id")
            .eq("user_id", str(current_user.user_id))
            .eq("role", OrgRole.OWNER.value)
            .execute()
        )
    except APIError as exc:
        raise InternalError from exc

    rows = cast("list[dict[str, Any]]", response.data or [])
    if len(rows) >= settings.FREE_TIER_ORG_LIMIT:
        raise SubscriptionRequiredError
