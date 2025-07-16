import uuid
from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import func

from src.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Campos para controlar los intentos de recuperación de contraseña
    reset_attempts = Column(Integer, default=0)
    last_reset_attempt = Column(DateTime(timezone=True), nullable=True)
    reset_lockout_until = Column(DateTime(timezone=True), nullable=True)

    # Campos para controlar los intentos fallidos de inicio de sesión y el bloqueo de la cuenta
    is_locked = Column(Boolean, server_default='false', nullable=False)
    failed_login_attempts = Column(Integer, server_default='0', nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)

    password_history = relationship("PasswordHistory", back_populates="user", cascade="all, delete-orphan")


class PasswordHistory(Base):
    __tablename__ = "password_history"

    id = Column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="password_history")


class UsedToken(Base):
    __tablename__ = "used_tokens"
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    token_type = Column(String, nullable=False)
    user_id = Column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    used_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
