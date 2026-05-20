"""GeoJSON validation, area computation, and overlap detection.

Uses Shapely for everything. In production with PostGIS available, the
spatial queries themselves run in the DB. In dev (SQLite) we read parcel
GeoJSON into memory and run Shapely intersections — fine for the
prototype's data volume (~thousands of parcels per district).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from shapely.geometry import Polygon, shape
from shapely.ops import transform
from pyproj import Transformer

# UTM Zone 36N (EPSG:32636) — Uganda lies entirely between 29°E and 35°E,
# which falls inside the zone's 30°E–36°E band. Linear units are metres, so
# Shapely's planar area is accurate-to-the-square-metre across the country.
# 1 hectare = 10,000 m².
_TO_METRES = Transformer.from_crs(
    "EPSG:4326", "EPSG:32636", always_xy=True
).transform


@dataclass
class GeometryValidationResult:
    valid: bool
    area_hectares: float
    centroid_lon: float
    centroid_lat: float
    reason: str | None


def parse_geojson(geometry: dict[str, Any] | str) -> Polygon:
    """Parse a GeoJSON Polygon (dict or string) into a Shapely polygon."""
    if isinstance(geometry, str):
        geometry = json.loads(geometry)
    if not isinstance(geometry, dict):
        raise ValueError("geometry must be a GeoJSON dict")
    if geometry.get("type") != "Polygon":
        raise ValueError(f"unsupported geometry type: {geometry.get('type')}")
    geom = shape(geometry)
    if not isinstance(geom, Polygon):
        raise ValueError("shapely did not produce a Polygon")
    return geom


def validate_geometry(
    geometry: dict[str, Any] | str,
    *,
    min_hectares: float = 0.0001,
    max_hectares: float = 10_000.0,
) -> GeometryValidationResult:
    """Validate shape, simplicity, and area sanity."""
    try:
        poly = parse_geojson(geometry)
    except Exception as exc:
        return GeometryValidationResult(False, 0.0, 0.0, 0.0, f"parse_error: {exc}")
    if not poly.is_valid:
        return GeometryValidationResult(False, 0.0, 0.0, 0.0, "polygon_not_valid")
    if not poly.is_simple:
        return GeometryValidationResult(False, 0.0, 0.0, 0.0, "polygon_not_simple")
    # Project to UTM 36N (metres) for accurate hectares (1 ha = 10_000 m²).
    try:
        projected = transform(_TO_METRES, poly)
        area_ha = projected.area / 10_000.0
    except Exception:
        # Fallback: rough degree-based estimate × 1° ≈ 111 km at the equator.
        area_ha = poly.area * (111_000.0 ** 2) / 10_000.0
    if not (min_hectares <= area_ha <= max_hectares):
        return GeometryValidationResult(
            False, area_ha, 0.0, 0.0, f"area_out_of_range: {area_ha:.4f}ha"
        )
    cx, cy = poly.centroid.x, poly.centroid.y
    return GeometryValidationResult(True, round(area_ha, 4), cx, cy, None)


def overlap_fraction(a: Polygon, b: Polygon) -> float:
    """Return the fraction of ``a`` covered by ``b`` (0.0–1.0)."""
    if not a.intersects(b):
        return 0.0
    inter = a.intersection(b)
    if a.area == 0:
        return 0.0
    return inter.area / a.area
