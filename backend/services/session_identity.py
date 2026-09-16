def session_user_payload(user) -> dict:
    """Return the minimal user identity needed to restore browser auth state."""
    return {
        "id": str(user.id),
        "email": user.email,
        "email_verified": getattr(user, "email_verified_at", None) is not None,
        "full_name": user.full_name,
        "tariff": None,
        "roles": [role.role for role in user.roles],
    }
