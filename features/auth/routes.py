from ninja import Router
from ninja.errors import HttpError

from common.response.response_builder import ResponseBuilder
from .schema import LoginRequest
from .service import AuthService

router = Router()


@router.post("/login")
def login(request, payload: LoginRequest):
    """Authenticate using mock credentials and return JWT on success."""
    token = AuthService.login(payload.username, payload.password)
    if not token:
        return ResponseBuilder.error("Invalid credentials", code="AUTH_FAILED"), 401

    return ResponseBuilder.success({"token": token, "role": "SalesRepresentative"})

@router.get("/health")
def health(request):
    return ResponseBuilder.success("running good")

