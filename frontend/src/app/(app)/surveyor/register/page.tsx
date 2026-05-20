"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { MapPin } from "lucide-react";
import { api, makeIdempotencyKey } from "@/lib/api";
import { useDistrictStore, DEMO_DISTRICTS } from "@/store/useDistrictStore";
import { Button } from "@/components/common/Button";

const MapParcelDrawer = dynamic(
  () =>
    import("@/components/map/MapParcelDrawer").then((m) => m.MapParcelDrawer),
  { ssr: false },
);

const DISTRICT_CODES: Record<number, string> = {
  1: "KCC",
  2: "WAK",
  3: "MIT",
  4: "GUL",
};

/**
 * Surveyor parcel registration — Act 2 of the showcase. Draw the polygon
 * on the district map; real-time Turf overlap detection flags conflicts
 * before the submit button enables.
 */
export default function SurveyorRegisterPage() {
  const districtId = useDistrictStore((s) => s.activeId);
  const [geometry, setGeometry] = useState<GeoJSON.Polygon | null>(null);
  const [areaHa, setAreaHa] = useState(0);
  const [subCounty, setSubCounty] = useState("");
  const [tenure, setTenure] = useState("MAILO");
  const [parcelNumber, setParcelNumber] = useState(0);

  const districtName =
    DEMO_DISTRICTS.find((d) => d.id === districtId)?.name ??
    `District ${districtId}`;
  const districtCode = DISTRICT_CODES[districtId] ?? "XXX";
  const upi = `UG-${districtCode}-${parcelNumber.toString().padStart(6, "0")}/2026`;

  const submit = useMutation({
    mutationFn: async () => {
      if (!geometry) throw new Error("Draw a polygon first");
      return api.post(
        "/v1/parcels",
        {
          parcel_id: upi,
          tenure_type: tenure,
          district_id: districtId,
          sub_county: subCounty || "Unknown",
          geometry,
        },
        makeIdempotencyKey(),
      );
    },
    onSuccess: () => toast.success(`Parcel ${upi} registered.`),
    onError: (err) =>
      toast.error(
        `Could not register: ${(err as { detail?: string }).detail ?? "error"}`,
      ),
  });

  const ready = Boolean(geometry) && parcelNumber > 0;

  return (
    <div className="space-y-6">
      <header className="border-b border-slate-200 pb-4">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          Surveyor console
        </p>
        <h1 className="font-serif text-2xl font-bold text-slate-900">
          Register a parcel
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">
          Draw the boundary on the <strong>{districtName}</strong> map.
          Real-time overlap detection flags any conflict with existing
          parcels before submission.
        </p>
      </header>

      <MapParcelDrawer
        onGeometry={(g, ha) => {
          setGeometry(g);
          setAreaHa(ha);
        }}
      />

      <section className="card-surface space-y-4">
        <header className="flex items-center gap-2 border-b border-slate-200 pb-3">
          <MapPin className="size-4 text-guard-700" aria-hidden />
          <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
            Parcel attributes
          </p>
        </header>
        <div className="grid gap-4 md:grid-cols-3">
          <label className="block space-y-1.5">
            <span className="field-label">Parcel number</span>
            <input
              type="number"
              value={parcelNumber || ""}
              onChange={(e) => setParcelNumber(Number(e.target.value))}
              className="field-input"
              placeholder="e.g. 24718"
            />
          </label>
          <label className="block space-y-1.5">
            <span className="field-label">Tenure type</span>
            <select
              value={tenure}
              onChange={(e) => setTenure(e.target.value)}
              className="field-input"
            >
              {["MAILO", "FREEHOLD", "LEASEHOLD", "CUSTOMARY"].map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
          </label>
          <label className="block space-y-1.5">
            <span className="field-label">Sub-county</span>
            <input
              type="text"
              value={subCounty}
              onChange={(e) => setSubCounty(e.target.value)}
              className="field-input"
              placeholder="e.g. Mityana TC"
            />
          </label>
          <Computed label="Calculated UPI" mono>
            {upi}
          </Computed>
          <Computed label="Calculated area">
            {areaHa.toFixed(4)} ha
          </Computed>
          <div className="flex items-end">
            <Button
              variant="primary"
              icon={<MapPin className="size-4" />}
              onClick={() => submit.mutate()}
              disabled={!ready}
              loading={submit.isPending}
            >
              Register parcel
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

function Computed({
  label,
  mono,
  children,
}: {
  label: string;
  mono?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <span className="field-label">{label}</span>
      <p
        className={`flex h-10 items-center rounded-md border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700 ${
          mono ? "font-mono" : "tabular-nums"
        }`}
      >
        {children}
      </p>
    </div>
  );
}
