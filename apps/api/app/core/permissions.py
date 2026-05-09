"""Single source of truth for organization role semantics.

Every role-based decision in the codebase routes through this module.
No router, repository, or schema may compare role strings inline.
"""

from enum import Enum

from app.exceptions import ForbiddenError


class OrgRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


_MANAGER_ROLES = frozenset({OrgRole.OWNER, OrgRole.ADMIN})


def can_manage_members(role: OrgRole) -> bool:
    return role in _MANAGER_ROLES


def can_remove_members(role: OrgRole) -> bool:
    return role in _MANAGER_ROLES


def can_invite(role: OrgRole) -> bool:
    return role in _MANAGER_ROLES


def can_manage_billing(role: OrgRole) -> bool:
    return role is OrgRole.OWNER


def can_delete_org(role: OrgRole) -> bool:
    return role is OrgRole.OWNER


def is_owner(role: OrgRole) -> bool:
    return role is OrgRole.OWNER


def assert_not_owner_removal(target_role: OrgRole) -> None:
    if target_role is OrgRole.OWNER:
        raise ForbiddenError(
            "org owner cannot be removed",
            code="cannot_remove_owner",
        )
