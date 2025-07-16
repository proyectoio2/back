import uuid
from fastapi import UploadFile
from typing import Optional, List

from src.storage.client import spaces_client
from src.storage.config import get_storage_config
from src.storage.constants import (
    DEFAULT_FOLDER, ALLOWED_IMAGE_TYPES,
    ERROR_FILE_TOO_LARGE, ERROR_INVALID_FILE_TYPE, ERROR_UPLOAD_FAILED
)
from src.storage.exceptions import (
    FileTooBigException, InvalidFileTypeException, UploadFailedException
)
from src.storage.schemas import StorageResponse

storage_config = get_storage_config()


class SpacesStorageService:
    def __init__(self):
        self.client = spaces_client
        self.max_image_size = storage_config.max_image_size
        self.bucket = storage_config.bucket
        self.endpoint = storage_config.endpoint
        self.cdn_endpoint = storage_config.cdn_endpoint

    async def upload_image(self, file: UploadFile, folder: str = DEFAULT_FOLDER, use_cdn: bool = True) -> StorageResponse:
        if not file.content_type.startswith("image/"):
            raise InvalidFileTypeException(ALLOWED_IMAGE_TYPES)
        
        content = await file.read()
        
        file_size = len(content)
        if file_size > self.max_image_size:
            max_size_mb = self.max_image_size / (1024 * 1024)
            raise FileTooBigException(max_size_mb)
        
        ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        filename = f"{uuid.uuid4()}.{ext}"
        
        object_key = f"{folder}/{filename}"
        
        try:
            self.client.put_object(
                key=object_key,
                body=content,
                content_type=file.content_type
            )
            url_base = self.cdn_endpoint if use_cdn and self.cdn_endpoint else self.endpoint
            url = f"{url_base}/{self.bucket}/{object_key}"
            
            return StorageResponse(
                url=url,
                filename=filename,
                content_type=file.content_type,
                size=file_size,
                folder=folder
            )
            
        except Exception as e:
            raise UploadFailedException(f"{ERROR_UPLOAD_FAILED}: {str(e)}")

    async def delete_file(self, object_key: str) -> bool:
        try:
            self.client.delete_object(key=object_key)
            return True
        except Exception as e:
            raise UploadFailedException(f"Error al eliminar el archivo: {str(e)}")

    async def list_files(self, prefix: str = "", delimiter: str = "/") -> List[str]:
        try:
            response = self.client.list_objects(prefix=prefix, delimiter=delimiter)
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append(obj['Key'])
            
            return files
        except Exception as e:
            raise UploadFailedException(f"Error al listar archivos: {str(e)}")


storage_service = SpacesStorageService()