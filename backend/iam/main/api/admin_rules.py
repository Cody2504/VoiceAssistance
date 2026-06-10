"""Pure validation for admin user-patch requests — stdlib-only so unit tests
run without the FastAPI/DB stack."""

VALID_ROLES = ("user", "admin")


def validate_admin_patch(
    actor_sub: str, target_id: str, role: str | None, is_active: bool | None
) -> tuple[int, str] | None:
    """Return (http_status, message) if the patch must be rejected, else None.

    Rules: at least one field; role limited to user/admin; an admin can never
    change their own role or active status (self-lockout guard).
    """
    if role is None and is_active is None:
        return 400, "Nothing to update: provide role and/or is_active"
    if role is not None and role not in VALID_ROLES:
        return 400, f"Invalid role: {role}"
    if str(actor_sub) == str(target_id):
        return 403, "Admins cannot change their own role or active status"
    return None
