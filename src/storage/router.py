from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, Path
from fastapi.responses import JSONResponse
from uuid import UUID

from src.auth.schemas import User
from src.auth.service import get_current_user
from src.storage.constants import (
    PLANT_IMAGES_FOLDER, GARDEN_IMAGES_FOLDER, IDENTIFICATION_FOLDER
)
from src.storage.exceptions import (
    FileTooBigException, InvalidFileTypeException, UploadFailedException
)
from src.storage.schemas import StorageResponse
from src.storage.service import storage_service

router = APIRouter()