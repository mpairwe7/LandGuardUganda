"use client";

import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import * as turf from "@turf/turf";
import { AlertTriangle } from "lucide-react";

interface Props {
  initialCenter?: [number, number];
  onGeometry: (geojson: GeoJSON.Polygon | null, areaHa: number) => void;
  existingParcels?: Array<{ parcel_id: string; geometry: GeoJSON.Polygon }>;
}

/**
 * Surveyor parcel drawer. Click 3+ points on the map → polygon closes
 * automatically. Real-time overlap detection turns the polygon red and
 * surfaces conflicting parcel IDs.
 *
 * For brevity in the prototype this is a simplified geometry editor.
 * Production should swap in @mapbox/mapbox-gl-draw with custom modes.
 */
export function MapParcelDrawer({
  initialCenter = [32.0419, 0.4017], // Mityana TC
  onGeometry,
  existingParcels = [],
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [points, setPoints] = useState<[number, number][]>([]);
  const [overlaps, setOverlaps] = useState<string[]>([]);

  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: initialCenter,
      zoom: 16,
    });
    mapRef.current = map;
    map.on("click", (e) => {
      setPoints((prev) => [...prev, [e.lngLat.lng, e.lngLat.lat]]);
    });
    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [initialCenter]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (points.length < 3) {
      if (map.getLayer("draft-fill")) map.removeLayer("draft-fill");
      if (map.getLayer("draft-outline")) map.removeLayer("draft-outline");
      if (map.getSource("draft")) map.removeSource("draft");
      onGeometry(null, 0);
      return;
    }
    const closed = [...points, points[0]!];
    const poly: GeoJSON.Polygon = { type: "Polygon", coordinates: [closed] };
    const feature = turf.feature(poly);
    const areaSqM = turf.area(feature);
    const areaHa = areaSqM / 10_000;

    const conflicts: string[] = [];
    for (const p of existingParcels) {
      try {
        const other = turf.feature(p.geometry);
        if (turf.booleanIntersects(feature, other)) {
          conflicts.push(p.parcel_id);
        }
      } catch {
        /* ignore malformed */
      }
    }
    setOverlaps(conflicts);

    // Status-aware fill: orange (status-flag) on overlap, green (guard-700) when clean.
    const fillColor = conflicts.length ? "#c2410c" : "#1a5223";
    const lineColor = conflicts.length ? "#9a3412" : "#08200d";
    if (!map.getSource("draft")) {
      map.addSource("draft", { type: "geojson", data: feature as never });
      map.addLayer({
        id: "draft-fill",
        type: "fill",
        source: "draft",
        paint: { "fill-color": fillColor, "fill-opacity": 0.3 },
      });
      map.addLayer({
        id: "draft-outline",
        type: "line",
        source: "draft",
        paint: { "line-color": lineColor, "line-width": 2 },
      });
    } else {
      (map.getSource("draft") as maplibregl.GeoJSONSource).setData(feature as never);
      map.setPaintProperty("draft-fill", "fill-color", fillColor);
      map.setPaintProperty("draft-outline", "line-color", lineColor);
    }
    onGeometry(poly, Number(areaHa.toFixed(4)));
  }, [points, existingParcels, onGeometry]);

  return (
    <div className="space-y-3">
      <div
        ref={containerRef}
        className="h-[420px] w-full overflow-hidden rounded-md border border-slate-200"
      />
      <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
        <p className="text-slate-600">
          {points.length < 3
            ? `Click ${3 - points.length} more point(s) on the map to close the polygon.`
            : `Polygon with ${points.length} vertices.`}
        </p>
        <div className="flex items-center gap-2">
          {overlaps.length > 0 && (
            <span className="pill-flag">
              <AlertTriangle className="size-3.5" aria-hidden />
              <span>
                Overlap with {overlaps.length} parcel
                {overlaps.length === 1 ? "" : "s"}
              </span>
            </span>
          )}
          <button
            type="button"
            onClick={() => setPoints([])}
            className="btn-secondary h-9 px-3 text-xs"
          >
            Reset
          </button>
        </div>
      </div>
      {overlaps.length > 0 && (
        <div className="card-surface state-flag space-y-1 text-xs">
          <p className="font-semibold text-status-flag">Conflicting parcels</p>
          <ul className="space-y-0.5">
            {overlaps.map((p) => (
              <li key={p} className="font-mono text-slate-700">
                • {p}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
