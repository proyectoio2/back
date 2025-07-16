from fastapi import Depends

from src.storage.service import SpacesStorageService, storage_service


def get_storage_service() -> SpacesStorageService:
    return storage_service