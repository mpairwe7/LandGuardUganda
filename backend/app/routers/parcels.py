"""Parcel CRUD + geo search."""

from __future__ import annotations

import json
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.audit import audit_emit
from app.auth import AuthContext, Role, require_role
from app.database import get_connection
from app.models.parcels import (
    GeoSearchRequest,
    ParcelCreateRequest,
    ParcelRecord,
)
from app.util.geo import overlap_fraction, parse_geojson, validate_geometry

router = APIRouter(prefix="/api/v1/parcels", tags=["parcels"])


def _row_to_parcel(row) -> ParcelRecord:
    return ParcelRecord(
        parcel_id=row[0],
        tenure_type=row[1],
        district_id=int(row[2]),
        sub_county=row[3],
        geometry=json.loads(row[4]),
        area_hectares=float(row[5]),
        current_owner_id=row[6],
        status=row[7],
        created_at=float(row[8]),
        updated_at=float(row[9]),
    )


@router.post("", response_model=ParcelRecord, status_code=201)
async def create_parcel(
    payload: ParcelCreateRequest,
    ctx: Annotated[AuthContext, Depends(require_role(Role.SURVEYOR, Role.REGISTRAR))],
) -> ParcelRecord:
    geom_check = validate_geometry(payload.geometry)
    if not geom_check.valid:
        raise HTTPException(status_code=422, detail=f"invalid geometry: {geom_check.reason}")
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT parcel_id FROM parcels WHERE parcel_id = ?",
            (payload.parcel_id,),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="parcel already registered")
        now = time.time()
        conn.execute(
            "INSERT INTO parcels (parcel_id, tenure_type, district_id, sub_county, "
            " geometry_geojson, area_hectares, current_owner_id, status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                payload.parcel_id,
                payload.tenure_type,
                payload.district_id,
                payload.sub_county,
                json.dumps(payload.geometry),
                geom_check.area_hectares,
                payload.current_owner_id,
                "ACTIVE",
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT parcel_id, tenure_type, district_id, sub_county, geometry_geojson, "
            " area_hectares, current_owner_id, status, created_at, updated_at "
            "FROM parcels WHERE parcel_id = ?",
            (payload.parcel_id,),
        ).fetchone()
    audit_emit(
        event_type="PARCEL_REGISTERED",
        payload={
            "parcel_id": payload.parcel_id,
            "tenure_type": payload.tenure_type,
            "area_hectares": geom_check.area_hectares,
            "sub_county": payload.sub_county,
        },
        district_id=payload.district_id,
        actor_user_id=ctx.user_id,
    )
    return _row_to_parcel(row)


@router.get("/{parcel_id:path}", response_model=ParcelRecord)
async def get_parcel(
    parcel_id: str,
    ctx: Annotated[AuthContext, Depends(require_role(*Role))],
) -> ParcelRecord:
    # ``:path`` converter — UPIs contain a ``/`` separator
    # (e.g. ``UG-MIT-024718/2026``) which Starlette would otherwise
    # treat as a route boundary and 404 on.
    with get_connection() as conn:
        row = conn.execute(
            "SELECT parcel_id, tenure_type, district_id, sub_county, geometry_geojson, "
            " area_hectares, current_owner_id, status, created_at, updated_at "
            "FROM parcels WHERE parcel_id = ?",
            (parcel_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="parcel not found")
    return _row_to_parcel(row)


@router.get("", response_model=list[ParcelRecord])
async def list_parcels(
    ctx: Annotated[AuthContext, Depends(require_role(*Role))],
    district_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    owner_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ParcelRecord]:
    where = []
    params: list[object] = []
    if district_id is not None:
        where.append("district_id = ?")
        params.append(district_id)
    if status:
        where.append("status = ?")
        params.append(status)
    if owner_id:
        where.append("current_owner_id = ?")
        params.append(owner_id)
    sql = (
        "SELECT parcel_id, tenure_type, district_id, sub_county, geometry_geojson, "
        " area_hectares, current_owner_id, status, created_at, updated_at FROM parcels"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_parcel(r) for r in rows]


@router.post("/search/geo", response_model=list[ParcelRecord])
async def geo_search(
    payload: GeoSearchRequest,
    ctx: Annotated[AuthContext, Depends(require_role(*Role))],
) -> list[ParcelRecord]:
    geom_check = validate_geometry(payload.geometry, min_hectares=0.00001)
    if not geom_check.valid:
        raise HTTPException(status_code=422, detail=f"invalid geometry: {geom_check.reason}")
    candidate = parse_geojson(payload.geometry)
    sql = (
        "SELECT parcel_id, tenure_type, district_id, sub_county, geometry_geojson, "
        " area_hectares, current_owner_id, status, created_at, updated_at FROM parcels"
    )
    params: list[object] = []
    if payload.district_id is not None:
        sql += " WHERE district_id = ?"
        params.append(payload.district_id)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    result: list[ParcelRecord] = []
    for row in rows:
        try:
            other = parse_geojson(row[4])
        except Exception:
            continue
        if payload.mode == "within":
            if other.within(candidate):
                result.append(_row_to_parcel(row))
        elif overlap_fraction(candidate, other) > 0.0:
            result.append(_row_to_parcel(row))
        if len(result) >= payload.limit:
            break
    return result
