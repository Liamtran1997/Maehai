from ninja.security import SessionAuth


class StaffAuth(SessionAuth):
    """Django session cookie + CSRF, restricted to staff users (shop owners and employees)."""

    def authenticate(self, request, key):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and user.is_staff and user.is_active:
            return user
        return None


staff_auth = StaffAuth()
