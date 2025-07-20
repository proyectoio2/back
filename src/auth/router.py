import hashlib
from datetime import timedelta, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer
from fastapi.templating import Jinja2Templates
from jose import jwt
from sqlalchemy.orm import Session

from src.auth import service, schemas, models
from src.auth.service import email_service, get_password_hash
from src.config import get_settings
from src.database import get_db
from src.validators.password import validate_password

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()

templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

settings = get_settings()


@router.post("/register", 
            response_model=schemas.UserResponse,
            responses={
                201: {"description": "Usuario creado exitosamente"},
                400: {"model": schemas.ErrorResponse, "description": "Datos inválidos"},
                409: {"model": schemas.ErrorResponse, "description": "Conflicto con datos existentes"},
                422: {"description": "Error de validación", "model": schemas.ValidationError}
            },
            status_code=status.HTTP_201_CREATED,
            summary="Registrar nuevo usuario")
async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)) -> dict:
    created_user = await service.create_user(db=db, user=user)
    return {
        "status_code": 201,
        "message": "Usuario registrado exitosamente",
        "data": created_user
    }


@router.post("/token", 
            response_model=schemas.LoginResponse,
            responses={
                200: {"description": "Login exitoso"},
                400: {"model": schemas.ErrorResponse, "description": "Datos inválidos"},
                401: {"model": schemas.ErrorResponse, "description": "No autorizado"},
                429: {"model": schemas.ErrorResponse, "description": "Demasiados intentos"},
                422: {"description": "Error de validación", "model": schemas.ValidationError}
            },
            summary="Iniciar sesión")
def login_for_access_token(
        login_data: schemas.LoginRequest,
        db: Session = Depends(get_db)
) -> dict:
    if not login_data.email or not login_data.password:
        raise HTTPException(
            status_code=400,
            detail="El email y la contraseña son requeridos"
        )
    user = service.authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Credenciales inválidas"
        )
    access_token = service.create_access_token(data={"sub": str(user.id)})
    refresh_token = service.create_refresh_token(data={"sub": str(user.id)})
    return {
        "status_code": 200,
        "message": "Login exitoso",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "refresh_token": refresh_token,
            "user": {
                "id": str(user.id),
                "email": user.email,
                "full_name": user.full_name,
                "phone_number": user.phone_number,
                "address": user.address,
                "is_superuser": user.is_superuser
            }
        }
    }


@router.post("/refresh", 
            response_model=schemas.RefreshTokenResponse,
            responses={
                200: {"description": "Token refrescado exitosamente"},
                400: {"model": schemas.ErrorResponse, "description": "Datos inválidos"},
                401: {"model": schemas.ErrorResponse, "description": "No autorizado"},
                422: {"description": "Error de validación", "model": schemas.ValidationError}
            },
            summary="Refrescar token de acceso")
def refresh_token(
        refresh_token: str = Form(..., description="Token de refresco"),
        db: Session = Depends(get_db)
) -> dict:
    # Validar que se proporcionó el token
    if not refresh_token:
        return JSONResponse(
            status_code=400,
            content={
                "status_code": 400,
                "message": "Datos inválidos",
                "detail": "Token de refresco no proporcionado"
            }
        )
    # Decodificar y validar el token
    try:
        payload = jwt.decode(
            refresh_token,
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if not user_id or token_type != "refresh":
            return JSONResponse(
                status_code=401,
                content={
                    "status_code": 401,
                    "message": "No autorizado",
                    "detail": "Token de refresco inválido"
                }
            )
    except jwt.ExpiredSignatureError:
        return JSONResponse(
            status_code=401,
            content={
                "status_code": 401,
                "message": "No autorizado",
                "detail": "Token de refresco expirado"
            }
        )
    except jwt.JWTError:
        return JSONResponse(
            status_code=401,
            content={
                "status_code": 401,
                "message": "No autorizado",
                "detail": "Token de refresco inválido"
            }
        )
    # Verificar que el usuario existe
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return JSONResponse(
            status_code=401,
            content={
                "status_code": 401,
                "message": "No autorizado",
                "detail": "Usuario no encontrado"
            }
        )
    # Generar nuevos tokens
    new_access_token = service.create_access_token(data={"sub": str(user.id)})
    new_refresh_token = service.create_refresh_token(data={"sub": str(user.id)})
    return {
        "status_code": 200,
        "message": "Token refrescado exitosamente",
        "data": {
            "access_token": new_access_token,
            "token_type": "bearer",
            "refresh_token": new_refresh_token,
            "user": {
                "id": str(user.id),
                "email": user.email,
            }
        }
    }


@router.post("/password-reset-request", 
            response_model=schemas.PasswordResetRequestResponse,
            responses={
                200: {"description": "Solicitud de restablecimiento enviada"},
                400: {"model": schemas.ErrorResponse, "description": "Datos inválidos"},
                429: {"model": schemas.ErrorResponse, "description": "Demasiados intentos"},
                422: {"description": "Error de validación", "model": schemas.ValidationError}
            },
            summary="Solicitar restablecimiento de contraseña")
async def request_password_reset(
        request: Request,
        reset_request: schemas.PasswordResetRequest,
        db: Session = Depends(get_db)
) -> dict:
    # Verificar si el usuario existe
    user = db.query(models.User).filter(models.User.email == reset_request.email).first()
    if not user:
        return {
            "status_code": 200,
            "message": "Solicitud de restablecimiento enviada",
            "data": {
                "detail": "Si existe una cuenta con ese email, recibirás instrucciones para restablecer tu contraseña"
            }
        }
    # Verificar intentos de restablecimiento
    if user.reset_attempts >= 3:
        if user.reset_lockout_until and user.reset_lockout_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=429,
                detail="Demasiados intentos. Por favor, intente más tarde"
            )
        # Resetear contadores si ya pasó el tiempo de bloqueo
        user.reset_attempts = 0
        user.reset_lockout_until = None
    # Generar y enviar token
    token = await service.create_password_reset_token(user)
    try:
        await email_service.send_password_reset_email(user.email, token)
    except Exception as e:
        print(f"Error al enviar email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error al enviar el email de restablecimiento"
        )
    # Incrementar contador de intentos
    user.reset_attempts = (user.reset_attempts or 0) + 1
    if user.reset_attempts >= 3:
        user.reset_lockout_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    db.commit()
    return {
        "status_code": 200,
        "message": "Solicitud de restablecimiento enviada",
        "data": {
            "detail": "Si existe una cuenta con ese email, recibirás instrucciones para restablecer tu contraseña"
        }
    }


@router.get("/password-reset",
            response_class=HTMLResponse,
            responses={
                200: {"description": "Formulario de restablecimiento o mensaje de error"},
                400: {"model": schemas.ErrorResponse, "description": "Token inválido o expirado"},
                401: {"model": schemas.ErrorResponse, "description": "No autorizado"}
            },
            summary="Mostrar formulario de restablecimiento")
async def get_password_reset_form(
        request: Request,
        token: str,
        db: Session = Depends(get_db)
) -> HTMLResponse:
    try:
        # Validar el token de restablecimiento
        token_data = service.validate_password_reset_form_token(token=token, db=db)

        # Si el token es válido, mostrar el formulario
        return templates.TemplateResponse(
            name="email/reset_password.html", 
            context={
                "request": request,
                "token": token
                }
            )

    except HTTPException as e:
        # Si el token es inválido o expirado, mostrar la página de error
        return templates.TemplateResponse(
            name="email/password_reset_expired.html", # Usar la nueva plantilla de expirado
            context={
                "request": request,
                "detail": e.detail # Pasar detalles si es necesario (opcional)
                }, 
            status_code=e.status_code
            )
    except Exception as e:
        # Manejo de otros errores inesperados
        print(f"Error inesperado al validar token: {e}")
        return templates.TemplateResponse(
             name="email/password_reset_expired.html", 
             context={
                 "request": request,
                 "detail": "Error interno del servidor."
                 }, 
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
             )


@router.post("/password-reset",
            response_model=schemas.PasswordResetResponse, # Aunque redirigimos, mantenemos el modelo para la documentación
            responses={
                200: {"description": "Redirección a página de éxito"},
                400: {"description": "Redirección a página de error (token inválido/expirado)"},
                422: {"description": "Error de validación", "model": schemas.ValidationError}
            },
            summary="Restablecer contraseña")
async def reset_password(
        token: str = Form(...),
        new_password: str = Form(...),
        db: Session = Depends(get_db)
) -> RedirectResponse:
    try:
        # Validar el token y restablecer la contraseña
        service.reset_password(token=token, new_password=new_password, db=db)

        # Si todo es exitoso, redirigir a la página de éxito
        return RedirectResponse(url="/auth/password-reset-success", status_code=status.HTTP_303_SEE_OTHER)

    except HTTPException as e:
        # Si hay un error (token inválido/expirado/usuario no encontrado), redirigir a la página de error
        print(f"Error en reset_password: {e.detail}")
        return RedirectResponse(url="/auth/password-reset-expired", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        # Manejo de otros errores inesperados
        print(f"Error inesperado al restablecer contraseña: {e}")
        return RedirectResponse(url="/auth/password-reset-expired", status_code=status.HTTP_303_SEE_OTHER) # Redirigir a error genérico


@router.get("/password-reset-success", response_class=HTMLResponse, summary="Página de éxito de restablecimiento")
async def password_reset_success(request: Request):
    return templates.TemplateResponse(name="email/password_reset_success.html", context={"request": request})


@router.get("/password-reset-expired", response_class=HTMLResponse, summary="Página de enlace inválido/expirado")
async def password_reset_expired(request: Request):
    return templates.TemplateResponse(name="email/password_reset_expired.html", context={"request": request})


@router.get("/me", 
            response_model=schemas.UserResponse,
            responses={
                200: {"description": "Datos del usuario obtenidos exitosamente"},
                401: {"model": schemas.ErrorResponse, "description": "No autorizado"},
                422: {"description": "Error de validación", "model": schemas.ValidationError}
            },
            summary="Obtener datos del usuario actual")
async def get_me(current_user: models.User = Depends(service.get_current_user)) -> dict:
    return {
        "status_code": 200,
        "message": "Datos del usuario obtenidos exitosamente",
        "data": {
            "id": str(current_user.id),
            "email": current_user.email,
            "full_name": current_user.full_name,
            "phone_number": current_user.phone_number,
            "address": current_user.address,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
            "created_at": current_user.created_at,
            "updated_at": current_user.updated_at
        }
    }


@router.put("/me", 
            response_model=schemas.UserUpdateResponse,
            responses={
                200: {"description": "Perfil actualizado exitosamente"},
                400: {"model": schemas.ErrorResponse, "description": "Datos inválidos"},
                401: {"model": schemas.ErrorResponse, "description": "No autorizado"},
                404: {"model": schemas.ErrorResponse, "description": "Usuario no encontrado"}
            },
            summary="Actualizar perfil de usuario")
def update_user_me(
        user_update: schemas.UserUpdate,
        current_user: schemas.User = Depends(service.get_current_user),
        db: Session = Depends(get_db)
) -> dict:
    updated_user = service.update_user(
        db=db,
        user_id=current_user.id,
        user_update=user_update,
        current_password=user_update.current_password
    )
    return {
        "status_code": 200,
        "message": "Perfil actualizado exitosamente",
        "data": updated_user
    }
