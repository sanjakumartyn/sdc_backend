from typing import Optional
from common.security.jwt_handler import JWTHandler


class AuthService:
    """Simple auth service using mock credentials for now."""

    # Mock user store: username -> {password, role, id}
    MOCK_USERS = {
        "salesrep": {"password": "password123", "role": "SalesRepresentative", "id": "1"}
    }

    @staticmethod
    def login(username: str, password: str) -> Optional[str]:
        user = AuthService.MOCK_USERS.get(username)
        if not user or user.get("password") != password:
            return None

        additional_claims = {"role": user.get("role"), "username": username}
        token = JWTHandler.create_token(user_id=user.get("id"), additional_claims=additional_claims)
        return token
