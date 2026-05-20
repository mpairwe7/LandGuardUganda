"""Shared Pydantic primitives — strict, extra='forbid'."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class StrictModel(BaseModel):
    """Project base: strict types, no extra keys."""

    model_config = ConfigDict(strict=True, extra="forbid", frozen=False)


class Pagination(StrictModel):
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(StrictModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

    @classmethod
    def of(cls, items: list[T], *, total: int, limit: int, offset: int) -> "PaginatedResponse[T]":
        return cls(items=items, total=total, limit=limit, offset=offset)
