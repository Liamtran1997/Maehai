from .permissions import PermissionAuth, account_auth, requires

# Kept for the few callers that only need "any logged-in staff member".
staff_auth = requires(None)

__all__ = ["PermissionAuth", "account_auth", "requires", "staff_auth"]
