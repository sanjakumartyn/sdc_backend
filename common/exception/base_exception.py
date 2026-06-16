from typing import Any, Optional, Dict


class APIException(Exception):
    """Base exception for all system-generated API errors."""
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_code: str = "BAD_REQUEST",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class NotFoundException(APIException):
    """Exception raised when a resource is not found."""
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=404,
            error_code="RESOURCE_NOT_FOUND",
            details=details
        )


class BadRequestException(APIException):
    """Exception raised for client request validation or processing issues."""
    def __init__(self, message: str = "Bad request parameter", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="BAD_REQUEST",
            details=details
        )


class UnauthorizedException(APIException):
    """Exception raised when the authentication check fails."""
    def __init__(self, message: str = "Authentication credentials not provided or invalid", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code="UNAUTHORIZED",
            details=details
        )


class ForbiddenException(APIException):
    """Exception raised when authorization checks fail."""
    def __init__(self, message: str = "You do not have permission to access this resource", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=403,
            error_code="FORBIDDEN",
            details=details
        )


class ServiceUnavailableException(APIException):
    """Exception raised when an upstream service cannot be reached."""
    def __init__(self, message: str = "Service temporarily unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            details=details
        )


class GroqApiKeyMissingException(APIException):
    """Exception raised when Groq is required but not configured."""
    def __init__(
        self,
        message: str = "Groq API key is required to generate the final answer",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=503,
            error_code="GROQ_API_KEY_MISSING",
            details=details,
        )


class GroqModelNotFoundException(APIException):
    """Exception raised when the configured Groq model is unavailable."""
    def __init__(
        self,
        message: str = "Configured Groq model is not available",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=503,
            error_code="GROQ_MODEL_NOT_FOUND",
            details=details,
        )


class GroqPayloadTooLargeException(APIException):
    """Exception raised when Groq rejects a request payload as too large."""
    def __init__(
        self,
        message: str = "Groq request payload is too large",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=503,
            error_code="GROQ_PAYLOAD_TOO_LARGE",
            details=details,
        )


class GroqDashboardJsonInvalidException(APIException):
    """Exception raised when Groq does not return valid dashboard JSON."""
    def __init__(
        self,
        message: str = "Unable to generate valid company analysis dashboard JSON",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=503,
            error_code="GROQ_DASHBOARD_JSON_INVALID",
            details=details,
        )
