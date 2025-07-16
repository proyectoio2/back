from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from src.database import Base

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# Import all models to ensure they are registered with SQLAlchemy
from src.auth.models import User, PasswordHistory, UsedToken
from src.gardens.models import Garden
from src.plants.models import Plant
from src.notes.models import PlantNote