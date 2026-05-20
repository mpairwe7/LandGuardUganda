"""Parcel HTTP models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator

from app.models.common import StrictModel
from app.util.ids import validate_upi

TenureType = Literal["MAILO", "FREEHOLD", "LEASEHOLD", "CUSTOMARY"]
ParcelStatus = Literal["ACTIVE", "DISPUTED", "FROZEN", "TRANSFERRED"]


class ParcelCreateRequest(StrictModel):
    parcel_id: str = Field(min_length=11, max_length=32)
    tenure_type: TenureType
    district_id: int = Field(ge=1)
    sub_county: str = Field(min_length=1, max_length=128)
    geometry: dict[str, Any]  # GeoJSON Polygon
    current_owner_id: str | None = None

    @field_validator("parcel_id")
    @classmethod
    def _check_upi(cls, v: str) -> str:
        if not validate_upi(v):
            raise ValueError("parcel_id must be UPI shape UG-DDD-NNNNNN/YYYY")
        return v

    @field_validator("geometry")
    @classmethod
    def _check_geometry_shape(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v.get("type") != "Polygon":
            raise ValueError("geometry.type must be 'Polygon'")
        if not isinstance(v.get("coordinates"), list):
            raise ValueError("geometry.coordinates must be a list")
        return v


class ParcelRecord(StrictModel):
    parcel_id: str
    tenure_type: TenureType
    district_id: int
    sub_county: str
    geometry: dict[str, Any]
    area_hectares: float
    current_owner_id: str | None
    status: ParcelStatus
    created_at: float
    updated_at: float


class GeoSearchRequest(StrictModel):
    geometry: dict[str, Any]
    mode: Literal["intersects", "within"] = "intersects"
    district_id: int | None = None
    limit: int = Field(default=50, ge=1, le=500)
