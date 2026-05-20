"use client";

import { useDistrictStore } from "@/store/useDistrictStore";
import { ReviewQueue } from "@/components/fraud/ReviewQueue";

/**
 * Officer review queue — the human-in-the-loop surface. The ReviewQueue
 * component renders its own header (count, policy reminder) so this page
 * is intentionally minimal.
 */
export default function OfficerPage() {
  const districtId = useDistrictStore((s) => s.activeId);
  return <ReviewQueue districtId={districtId} />;
}
