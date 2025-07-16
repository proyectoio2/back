from typing import List, Dict, Any
import os
from uuid import UUID
from fastapi import UploadFile

from src.storage.schemas import StorageResponse


def get_file_extension(filename: str) -> str:
    return filename.split(".")[-1] if "." in filename else ""


def get_object_key_from_url(url: str, bucket: str, endpoint: str) -> str:
    base_url = f"{endpoint}/{bucket}/"
    if url.startswith(base_url):
        return url[len(base_url):]
    return ""


def generate_object_key(
    user_id: UUID, 
    resource_id: UUID = None, 
    folder: str = "uploads", 
    filename: str = None
) -> str:
    if resource_id:
        return f"{folder}/{user_id}/{resource_id}/{filename}"
    return f"{folder}/{user_id}/{filename}"


def format_storage_response(
    url: str, 
    filename: str, 
    content_type: str, 
    size: int, 
    folder: str
) -> StorageResponse:
    return StorageResponse(
        url=url,
        filename=filename,
        content_type=content_type,
        size=size,
        folder=folder
    ) 