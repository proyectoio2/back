from fastapi import HTTPException, status

class AuthException(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)

class InvalidCredentialsException(AuthException):
    def __init__(self):
        super().__init__(
            detail="Credenciales inválidas",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

class UserAlreadyExistsException(AuthException):
    def __init__(self):
        super().__init__(
            detail="El usuario ya existe",
            status_code=status.HTTP_400_BAD_REQUEST
        )

class UserNotFoundException(AuthException):
    def __init__(self):
        super().__init__(
            detail="Usuario no encontrado",
            status_code=status.HTTP_404_NOT_FOUND
        )

class InvalidTokenException(AuthException):
    def __init__(self, message: str = "Token inválido"):
        super().__init__(
            detail=message,
            status_code=status.HTTP_401_UNAUTHORIZED
        )

class TokenExpiredException(AuthException):
    def __init__(self):
        super().__init__(
            detail="Token expirado",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

class PasswordHistoryException(AuthException):
    def __init__(self):
        super().__init__(
            detail="La nueva contraseña no puede ser igual a contraseñas utilizadas anteriormente",
            status_code=status.HTTP_400_BAD_REQUEST
        )

class RateLimitException(AuthException):
    def __init__(self, message: str = "Demasiados intentos. Por favor, espera antes de intentarlo nuevamente."):
        super().__init__(
            detail=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )

class InvalidPasswordException(AuthException):
    def __init__(self, message: str = "La contraseña no cumple con los requisitos de seguridad"):
        super().__init__(
            detail=message,
            status_code=status.HTTP_400_BAD_REQUEST
        ) 