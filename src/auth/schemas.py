from datetime import datetime
from typing import Optional, Union, List, Dict, Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, constr, field_validator, ConfigDict, Field

from src.validators.password import validate_password


class UserBase(BaseModel):
    email: EmailStr
    full_name: constr(min_length=3, max_length=100)
    phone_number: constr(min_length=7, max_length=20)
    address: constr(min_length=5, max_length=255)


class UserCreate(UserBase):
    password: constr(min_length=8)

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[constr(min_length=3, max_length=100)] = None
    phone_number: Optional[constr(min_length=7, max_length=20)] = None
    address: Optional[constr(min_length=5, max_length=255)] = None
    current_password: Optional[constr(min_length=8)] = None
    new_password: Optional[constr(min_length=8)] = None

    @field_validator('new_password')
    @classmethod
    def validate_new_password_strength(cls, v):
        if v is not None:
            is_valid, error_message = validate_password(v)
            if not is_valid:
                raise ValueError(error_message)
        return v


class User(UserBase):
    id: UUID
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str


class TokenData(BaseModel):
    user_id: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str
    new_password: constr(min_length=8)

    @field_validator('new_password')
    @classmethod
    def validate_new_password_strength(cls, v):
        is_valid, error_message = validate_password(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class BaseResponse(BaseModel):
    status_code: int
    message: str

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseResponse):
    detail: str


class SuccessResponse(BaseResponse):
    data: Optional[dict] = None


class LoginResponse(SuccessResponse):
    data: dict


class RefreshTokenResponse(SuccessResponse):
    data: dict


class UserResponse(SuccessResponse):
    data: User


class PasswordResetRequestResponse(SuccessResponse):
    pass


class PasswordResetResponse(SuccessResponse):
    pass


class UserUpdateResponse(BaseModel):
    status_code: int
    message: str
    data: User

    model_config = ConfigDict(from_attributes=True)


class UserCreateResponse(BaseModel):
    status_code: int
    message: str
    data: User

    model_config = ConfigDict(from_attributes=True)


class ValidationErrorItem(BaseModel):
    loc: List[Union[str, int]] = Field(
        ...,
        description="Ubicación del error en el objeto de entrada",
        examples=["body", "email"]
    )
    msg: str = Field(
        ...,
        description="Mensaje de error",
        examples="invalid email format"
    )
    type: str = Field(
        ...,
        description="Tipo de error",
        examples="value_error.email"
    )


class ValidationError(BaseModel):
    status_code: int = Field(
        422,
        description="Código de estado HTTP",
        examples=422
    )
    message: str = Field(
        "Error de validación",
        description="Mensaje general del error",
        examples="Error de validación"
    )
    detail: List[Dict[str, Any]] = Field(
        ...,
        description="Lista de errores de validación",
        examples=[{
            "loc": ["body", "email"],
            "msg": "invalid email format",
            "type": "value_error.email"
        }]
    )
