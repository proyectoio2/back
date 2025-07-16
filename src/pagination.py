from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar('T')

class PaginationParams(BaseModel):
    page: int = 1
    size: int = 10

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int

def paginate(
    items: list[T],
    total: int,
    page: int,
    size: int
) -> PaginatedResponse[T]:
    return PaginatedResponse[T](
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    ) 