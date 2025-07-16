from pydantic import BaseModel
from typing import Optional, List


class StorageResponse(BaseModel):
    url: str
    filename: str
    content_type: str
    size: int
    folder: str


class StorageListResponse(BaseModel):
    items: List[StorageResponse]
    total: int 