from app.exceptions import ConflictError

VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["sent", "void"],
    "sent": ["disputed", "paid", "void", "overdue"],
    "disputed": ["resolved", "void"],
    "resolved": ["paid", "void"],
    "paid": [],
    "void": [],
    "overdue": ["paid", "void"],
}


def assert_transition(current: str, target: str) -> None:
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ConflictError(
            f"cannot transition from '{current}' to '{target}'",
            code="invalid_status_transition",
        )
