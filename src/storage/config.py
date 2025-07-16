from pydantic import BaseModel
from src.config import get_settings

settings = get_settings()

class StorageConfig(BaseModel):
    key: str = settings.DO_SPACES_KEY
    secret: str = settings.DO_SPACES_SECRET
    endpoint: str = settings.DO_SPACES_ENDPOINT
    cdn_endpoint: str = settings.DO_SPACES_CDN_ENDPOINT if hasattr(settings, 'DO_SPACES_CDN_ENDPOINT') else settings.DO_SPACES_ENDPOINT
    region: str = settings.DO_SPACES_REGION
    bucket: str = settings.DO_SPACES_BUCKET
    max_image_size: int = settings.DO_SPACES_MAX_IMAGE_SIZE


def get_storage_config() -> StorageConfig:
    return StorageConfig()