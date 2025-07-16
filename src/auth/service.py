import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import or_
import secrets
import hmac

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from passlib.context import CryptContext

from src.auth import models, schemas, emails, exceptions, utils
from src.config import get_settings
from src.database import get_db
from src.validators.password import validate_password

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
email_service = emails.EmailService()
security = HTTPBearer()

MAX_RESET_ATTEMPTS = 4
BASE_LOCKOUT_MINUTES = 5
MAX_LOCKOUT_MINUTES = 60


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = utils.get_utc_now() + expires_delta
    else:
        expire = utils.get_future_datetime(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = utils.get_future_datetime(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def create_password_reset_token(data: dict | models.User) -> str:
    if isinstance(data, models.User):
        to_encode = {"sub": str(data.id)}
    else:
        to_encode = data.copy()
    expire = utils.get_future_datetime(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "password_reset"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def authenticate_user(db: Session, email: str, password: str) -> models.User:
    """
    Autenticar usuario solo por email.
    """
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )

    # Verificar si la cuenta está bloqueada
    if user.is_locked and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining_time = user.locked_until - datetime.now(timezone.utc)
        minutes = int(remaining_time.total_seconds() / 60)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Demasiados intentos fallidos. Por favor, intente nuevamente en {minutes} minutos"
        )
    elif user.is_locked and (not user.locked_until or user.locked_until <= datetime.now(timezone.utc)):
        # Si el bloqueo expiró, desbloquear la cuenta
        user.is_locked = False
        user.failed_login_attempts = 0
        user.locked_until = None
        db.commit()

    # Verificar contraseña
    if not verify_password(password, user.hashed_password):
        # Incrementar intentos fallidos de inicio de sesión
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        
        # Calcular tiempo de bloqueo incremental
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            # Tiempo base de bloqueo
            lockout_minutes = settings.ACCOUNT_LOCKOUT_MINUTES
            # Incrementar el tiempo por cada bloqueo adicional
            additional_attempts = user.failed_login_attempts - settings.MAX_LOGIN_ATTEMPTS
            lockout_minutes = lockout_minutes * (2 ** additional_attempts)  # Duplicar el tiempo por cada bloqueo adicional
            
            user.is_locked = True
            user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=lockout_minutes)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Demasiados intentos fallidos. Por favor, intente nuevamente en {lockout_minutes} minutos"
            )
        
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )

    # Si la autenticación es exitosa, resetear los intentos
    user.failed_login_attempts = 0
    user.is_locked = False
    user.locked_until = None
    db.commit()

    return user


async def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    # Validar formato de email
    if not user.email or "@" not in user.email:
        raise HTTPException(
            status_code=400,
            detail="El formato del email no es válido"
        )
    # Validar campos obligatorios
    if len(user.full_name) < 3:
        raise HTTPException(
            status_code=400,
            detail="El nombre completo debe tener al menos 3 caracteres"
        )
    if len(user.phone_number) < 7:
        raise HTTPException(
            status_code=400,
            detail="El número de celular debe tener al menos 7 dígitos"
        )
    if len(user.address) < 5:
        raise HTTPException(
            status_code=400,
            detail="La dirección debe tener al menos 5 caracteres"
        )
    if len(user.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="La contraseña debe tener al menos 8 caracteres"
        )
    # Verificar si el email ya existe
    existing_email = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_email:
        raise HTTPException(
            status_code=409,
            detail="El email ya está registrado por otro usuario"
        )
    # Verificar si el número de celular ya existe
    existing_phone = db.query(models.User).filter(models.User.phone_number == user.phone_number).first()
    if existing_phone:
        raise HTTPException(
            status_code=409,
            detail="El número de celular ya está registrado por otro usuario"
        )
    try:
        hashed_password = get_password_hash(user.password)
        db_user = models.User(
            email=user.email,
            full_name=user.full_name,
            phone_number=user.phone_number,
            address=user.address,
            hashed_password=hashed_password
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        password_history = models.PasswordHistory(
            user_id=db_user.id,
            hashed_password=hashed_password
        )
        db.add(password_history)
        db.commit()
        try:
            await email_service.send_welcome_email(db_user.email, db_user.full_name)
        except Exception as email_error:
            print(f"Error al enviar email de bienvenida: {str(email_error)}")
        return db_user
    except SQLAlchemyError as e:
        db.rollback()
        if "duplicate key value violates unique constraint" in str(e):
            raise HTTPException(
                status_code=409,
                detail="Ya existe un usuario con ese email o número de celular"
            )
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor al crear el usuario"
        )


def update_user(
        db: Session,
        user_id: int,
        user_update: schemas.UserUpdate,
        current_password: Optional[str] = None
) -> models.User:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado"
        )
    update_data = user_update.model_dump(exclude_unset=True)
    if "new_password" in update_data:
        if not current_password:
            raise HTTPException(
                status_code=400,
                detail="Se requiere la contraseña actual para cambiarla"
            )
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=400,
                detail="La contraseña actual es incorrecta"
            )
        hashed_new_password = get_password_hash(update_data["new_password"])
        recent_passwords = db.query(models.PasswordHistory).filter(
            models.PasswordHistory.user_id == user_id
        ).order_by(models.PasswordHistory.created_at.desc()).limit(3).all()
        for old_password in recent_passwords:
            if verify_password(update_data["new_password"], old_password.hashed_password):
                raise HTTPException(
                    status_code=400,
                    detail="La nueva contraseña no puede ser igual a una de las últimas 3 contraseñas utilizadas"
                )
        user.hashed_password = hashed_new_password
        db.add(models.PasswordHistory(user_id=user_id, hashed_password=hashed_new_password))
        del update_data["new_password"]
    if "email" in update_data and update_data["email"] != user.email:
        existing_user = db.query(models.User).filter(models.User.email == update_data["email"]).first()
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="El email ya está registrado por otro usuario"
            )
    if "phone_number" in update_data and update_data["phone_number"] != user.phone_number:
        existing_user = db.query(models.User).filter(models.User.phone_number == update_data["phone_number"]).first()
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="El número de celular ya está registrado por otro usuario"
            )
    for key, value in update_data.items():
        setattr(user, key, value)
    try:
        db.commit()
        db.refresh(user)
        return user
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Error al actualizar el perfil. Por favor, intente nuevamente"
        )


def delete_user(db: Session, user_id: int) -> bool:
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return False

    db.delete(db_user)
    db.commit()
    return True


async def request_password_reset(db: Session, email: str) -> bool:
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return False

    # Verificar límites de intentos
    _check_reset_rate_limits(db, user)

    # Invalidar tokens de restablecimiento anteriores para este usuario
    invalidate_previous_tokens(db, user.id, "password_reset")

    # Crear nuevo token
    token = await create_password_reset_token(user)
    
    # Enviar email
    success = await _send_password_reset_email(email, token)
    if not success:
        return False

    # Actualizar contadores
    user.reset_attempts = (user.reset_attempts or 0) + 1
    if user.reset_attempts >= 3:
        user.reset_lockout_until = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    db.commit()
    return True


def _check_reset_rate_limits(db: Session, user: models.User) -> None:
    """
    Verifica y aplica límites de intentos de restablecimiento de contraseña.
    
    Args:
        db: Sesión de la base de datos
        user: Usuario que solicita el restablecimiento
        
    Raises:
        HTTPException: Si se excede el límite de intentos
    """
    # Si no hay intentos previos, inicializar contador
    if user.reset_attempts is None:
        user.reset_attempts = 0
    
    # Si hay demasiados intentos y el bloqueo aún es válido
    if user.reset_attempts >= 3:
        if user.reset_lockout_until and user.reset_lockout_until > datetime.now(timezone.utc):
            remaining_minutes = int((user.reset_lockout_until - datetime.now(timezone.utc)).total_seconds() / 60)
            raise HTTPException(
                status_code=429,
                detail=f"Demasiados intentos. Por favor, espere {remaining_minutes} minutos antes de intentar nuevamente."
            )
        # Si el bloqueo expiró, resetear contadores
        user.reset_attempts = 0
        user.reset_lockout_until = None
        db.commit()


def _create_new_reset_token(db: Session, user: models.User) -> str:
    """
    Invalida los tokens anteriores de restablecimiento y crea uno nuevo.
    
    Args:
        db: Sesión de la base de datos
        user: Usuario para el que se crea el token
        
    Returns:
        str: Token de restablecimiento generado
    """
    # Invalidar cualquier token anterior para este usuario
    invalidate_previous_tokens(db, user.id, "password_reset")

    # Crear nuevo token
    reset_token = create_password_reset_token({"sub": str(user.id)})
    db.commit()

    return reset_token


async def _send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """
    Envía un email con el enlace para restablecer la contraseña.
    
    Args:
        to_email: Email del destinatario
        reset_token: Token de restablecimiento
        
    Returns:
        bool: True si el email se envió correctamente, False en caso contrario
    """
    try:
        await email_service.send_password_reset_email(to_email, reset_token)
        return True
    except Exception as e:
        print(f"Error al enviar email: {str(e)}")
        return False


def invalidate_previous_tokens(db: Session, user_id: UUID, token_type: str) -> None:
    """
    Marca todos los tokens existentes del tipo especificado como utilizados para un usuario.
    Esto se usa para invalidar tokens anteriores cuando se emite uno nuevo.
    """
    # Crear un identificador único para la invalidación
    invalidation_data = f"invalidation_{token_type}_{user_id}_{utils.get_utc_now().isoformat()}"
    
    # Usar Blake2b seguro en lugar de SHA-256 simple
    token_hash = _create_secure_token_hash(invalidation_data)
    
    invalidation_token = models.UsedToken(
        token_hash=token_hash,
        token_type=f"invalidation_{token_type}",
        user_id=user_id
    )
    db.add(invalidation_token)
    db.commit()


def is_token_valid(db: Session, token: str, user_id: UUID, token_type: str) -> bool:
    """
    Verifica si un token es válido: no ha sido utilizado y no ha sido invalidado por
    una solicitud posterior.
    """
    # Usar Blake2b seguro para crear el hash del token
    token_hash = _create_secure_token_hash(token)
    
    used_token = db.query(models.UsedToken).filter(
        models.UsedToken.token_hash == token_hash
    ).first()

    if used_token:
        return False

    if token_type == "password_reset":
        return True

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if 'iat' not in payload:  # Si no tiene fecha de emisión, usamos la fecha de expiración
            # Estimamos la fecha de emisión basada en la expiración y duración estándar
            if 'exp' in payload and payload.get('type') == token_type:
                estimated_iat = payload['exp'] - (settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES * 60)
            else:
                return False  # No podemos determinar emisión - no válido
        else:
            estimated_iat = payload['iat']

        # Buscar tokens de invalidación posterior a la emisión de este token
        invalidation_tokens = db.query(models.UsedToken).filter(
            models.UsedToken.user_id == user_id,
            models.UsedToken.token_type == f"invalidation_{token_type}",
            models.UsedToken.used_at > datetime.fromtimestamp(estimated_iat)
        ).all()

        if invalidation_tokens:
            return False

    except jwt.ExpiredSignatureError:
        return False
    except jwt.JWTError:
        return False

    return True


def reset_password(db: Session, token: str, new_password: str) -> bool:
    """
    Restablece la contraseña de un usuario utilizando un token de restablecimiento.
    
    Args:
        db: Sesión de la base de datos
        token: Token de restablecimiento
        new_password: Nueva contraseña
        
    Returns:
        bool: True si la contraseña se restableció correctamente
        
    Raises:
        InvalidTokenException: Si el token no es válido o ya fue utilizado
        TokenExpiredException: Si el token ha expirado
        UserNotFoundException: Si no se encuentra el usuario
        InvalidPasswordException: Si la contraseña no cumple con los requisitos
        PasswordHistoryException: Si la contraseña está en el historial reciente
    """
    try:
        # Validar el token y obtener el usuario
        user = _validate_reset_token(db, token)

        # Validar los requisitos de la contraseña
        _validate_password_requirements(new_password)

        # Verificar que la contraseña no esté en el historial reciente
        _check_password_history(db, user, new_password)

        # Actualizar la contraseña del usuario
        _update_user_password(db, user, new_password, token)

        return True
    except jwt.ExpiredSignatureError:
        raise exceptions.TokenExpiredException()
    except jwt.JWTError:
        raise exceptions.InvalidTokenException()


def _validate_reset_token(db: Session, token: str) -> models.User:
    """
    Válida un token de restablecimiento y devuelve el usuario asociado.
    
    Args:
        db: Sesión de la base de datos
        token: Token de restablecimiento
        
    Returns:
        models.User: Usuario asociado al token
        
    Raises:
        InvalidTokenException: Si el token no es válido o ya fue utilizado
        UserNotFoundException: Si no se encuentra el usuario
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    if payload.get("type") != "password_reset":
        raise exceptions.InvalidTokenException()

    user_id: str = payload.get("sub")
    if user_id is None:
        raise exceptions.InvalidTokenException()

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise exceptions.UserNotFoundException()

    # Verificar si el token ya ha sido utilizado usando Blake2b seguro
    token_hash = _create_secure_token_hash(token)
    used_token = db.query(models.UsedToken).filter(
        models.UsedToken.token_hash == token_hash
    ).first()

    if used_token:
        raise exceptions.InvalidTokenException(
            "Este enlace ya ha sido utilizado para restablecer tu contraseña. Por favor solicita un nuevo enlace si lo necesitas.")

    return user


def _validate_password_requirements(new_password: str) -> None:
    """
    Válida que la contraseña cumpla con los requisitos de seguridad.
    
    Args:
        new_password: Contraseña a validar
        
    Raises:
        InvalidPasswordException: Si la contraseña no cumple con los requisitos
    """
    if len(new_password) < 8:
        raise exceptions.InvalidPasswordException("La contraseña debe tener al menos 8 caracteres")

    is_valid, error_message = validate_password(new_password)
    if not is_valid:
        raise exceptions.InvalidPasswordException(error_message)


def _check_password_history(db: Session, user: models.User, new_password: str) -> None:
    """
    Verifica que la contraseña no esté en el historial reciente del usuario.
    
    Args:
        db: Sesión de la base de datos
        user: Usuario
        new_password: Nueva contraseña
        
    Raises:
        PasswordHistoryException: Si la contraseña está en el historial reciente
    """
    recent_passwords = db.query(models.PasswordHistory).filter(
        models.PasswordHistory.user_id == user.id
    ).order_by(models.PasswordHistory.created_at.desc()).limit(
        settings.PASSWORD_HISTORY_SIZE
    ).all()

    for old_password in recent_passwords:
        if verify_password(new_password, old_password.hashed_password):
            raise exceptions.PasswordHistoryException()


def _update_user_password(db: Session, user: models.User, new_password: str, token: str) -> None:
    """
    Actualiza la contraseña del usuario y registra el cambio.
    
    Args:
        db: Sesión de la base de datos
        user: Usuario
        new_password: Nueva contraseña
        token: Token utilizado para el restablecimiento
    """
    # Cifrar la nueva contraseña
    hashed_new_password = get_password_hash(new_password)

    # Actualizar la contraseña del usuario
    user.hashed_password = hashed_new_password

    # Registrar la nueva contraseña en el historial
    password_history = models.PasswordHistory(
        user_id=user.id,
        hashed_password=hashed_new_password
    )
    db.add(password_history)

    # Marcar el token como utilizado usando Blake2b seguro
    token_hash = _create_secure_token_hash(token)
    used_token = models.UsedToken(
        token_hash=token_hash,
        token_type="password_reset",
        user_id=user.id
    )
    db.add(used_token)

    # Reiniciar contadores de intentos
    user.reset_attempts = 0
    user.reset_lockout_until = None

    db.commit()


def get_user_from_token(db: Session, token: str) -> models.User:
    """
    Válida un token y devuelve el usuario asociado.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type", "")

        if user_id is None:
            raise exceptions.InvalidTokenException()

        if token_type not in ["refresh", "access"]:
            raise exceptions.InvalidTokenException("Token inválido: se requiere un token de acceso o refresco")

        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user is None:
            raise exceptions.UserNotFoundException()

        return user
    except jwt.ExpiredSignatureError:
        raise exceptions.TokenExpiredException()
    except jwt.JWTError:
        raise exceptions.InvalidTokenException()


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
) -> models.User:
    try:
        token = credentials.credentials
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type", "access")

        if user_id is None:
            raise exceptions.InvalidCredentialsException()

        if token_type != "access":
            raise exceptions.InvalidTokenException("Token inválido: se requiere un token de acceso")

    except jwt.ExpiredSignatureError:
        raise exceptions.TokenExpiredException()
    except jwt.JWTError:
        raise exceptions.InvalidTokenException()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise exceptions.UserNotFoundException()

    return user


def validate_password_reset_form_token(db: Session, token: str) -> models.User:
    """
    Válida un token para el formulario de restablecimiento de contraseña y devuelve el usuario.
    
    Args:
        db: Sesión de la base de datos
        token: Token de restablecimiento
        
    Returns:
        models.User: El usuario asociado al token si es válido.
        
    Raises:
        HTTPException: Si el token no es válido por cualquier motivo.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        # Verificar que sea un token de restablecimiento de contraseña
        if payload.get("type") != "password_reset":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este enlace de restablecimiento de contraseña no es válido."
            )

        # Verificar que contenga información de usuario
        user_id_str = payload.get("sub") # Obtener como string
        if user_id_str is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este enlace de restablecimiento de contraseña no contiene información de usuario."
            )

        try:
            user_id = UUID(user_id_str) # Convertir a UUID
        except ValueError:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato de ID de usuario inválido en el token."
            )

        # Buscar el usuario
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No se encontró ningún usuario asociado a este enlace."
            )

        # Verificar si el token ya ha sido utilizado usando Blake2b seguro
        token_hash = _create_secure_token_hash(token)
        used_token = db.query(models.UsedToken).filter(
            models.UsedToken.token_hash == token_hash
        ).first()

        if used_token:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este enlace ya ha sido utilizado para restablecer la contraseña. Por favor, solicita uno nuevo si necesitas cambiar tu contraseña."
            )

        # Verificar si ha sido invalidado por un token más reciente
        if not is_token_valid(db, token, user.id, "password_reset"):
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este enlace ya no es válido porque se ha solicitado uno más reciente. Por favor, utiliza el enlace más reciente que enviamos a tu correo."
            )

        # Token válido, devolver el usuario
        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este enlace de restablecimiento de contraseña ha expirado. Por favor, solicita uno nuevo."
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este enlace de restablecimiento de contraseña no es válido o ha sido modificado."
        )
    except Exception as e:
        # Capturar cualquier otro error inesperado durante la validación
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno del servidor al validar el token de restablecimiento."
        )


def _create_secure_token_hash(token: str) -> str:
    """
    Crea un hash seguro para tokens usando Blake2b con clave secreta.
    Blake2b es más rápido y seguro que SHA-256 para identificadores únicos.
    """
    try:
        # Usar Blake2b con la SECRET_KEY como clave
        secret_key = settings.SECRET_KEY.encode('utf-8')[:64]  # Blake2b acepta hasta 64 bytes
        token_bytes = token.encode('utf-8')
        
        # Blake2b con clave es criptográficamente seguro y rápido
        return hashlib.blake2b(token_bytes, key=secret_key, digest_size=32).hexdigest()
    except Exception:
        # Fallback a HMAC-SHA256 si Blake2b no está disponible
        secret_key = settings.SECRET_KEY.encode('utf-8')
        token_bytes = token.encode('utf-8')
        return hmac.new(secret_key, token_bytes, hashlib.sha256).hexdigest()


def generate_password_reset_token(self, db: Session, email: str) -> str:
    """
    Generar token seguro para restablecer contraseña.
    """
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise exceptions.UserNotFoundException()

    # Generar token aleatorio seguro
    token = secrets.token_urlsafe(32)
    
    # Crear hash del token usando la función segura
    token_hash = _create_secure_token_hash(token)
    
    # Guardar el hash del token en la base de datos
    user.password_reset_token = token_hash
    user.password_reset_token_expires = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    db.commit()
    
    return token


def verify_password_reset_token(self, db: Session, token: str) -> models.User:
    """
    Verificar token de restablecimiento de contraseña.
    """
    # Crear hash del token usando la función segura
    token_hash = _create_secure_token_hash(token)
    
    user = db.query(models.User).filter(
        models.User.password_reset_token == token_hash,
        models.User.password_reset_token_expires > datetime.now(timezone.utc)
    ).first()
    
    if not user:
        raise exceptions.InvalidTokenException()
            
    return user
