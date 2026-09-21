"""
Global Response Schemas

Pydantic models for global response schemas.
"""

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class GenericResponse(BaseModel, Generic[T]):
    success: bool = True
    message: Optional[str] = None
    data: Optional[T] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    total: int
    limit: int
    offset: int
    data: List[T]
