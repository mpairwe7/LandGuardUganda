import Link from "next/link";
import { Lock } from "lucide-react";
import { DemoControlPanel } from "@/components/demo/DemoControlPanel";

interface SearchParams {
  demo?: string;
}

/**
 * Demo gate. The control panel is dangerous (kill RPC, force flush) and
 * lives behind a query-string token so it can't be reached accidentally
 * from production navigation.
 */
export default async function DemoPage(props: {
  searchParams: Promise<SearchParams>;
}) {
  const sp = await props.searchParams;
  const gated = sp.demo === "1";

  if (!gated) {
    return (
      <main className="mx-auto flex min-h-screen max-w-citizen items-center px-6 py-16">
        <div className="card-elevated mx-auto w-full max-w-md space-y-3">
          <div className="flex items-start gap-3">
            <span className="rounded-md bg-status-pending/10 p-2 text-status-pending">
              <Lock className="size-5" aria-hidden />
            </span>
            <div>
              <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
                Demo orchestration
              </p>
              <h1 className="font-serif text-lg font-semibold text-slate-900">
                Showcase control panel
              </h1>
            </div>
          </div>
          <p className="text-sm leading-relaxed text-slate-700">
            Append{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800">
              ?demo=1
            </code>{" "}
            to this URL to access. The panel exposes the showcase
            orchestration controls — kill / restore the blockchain RPC,
            force an anchor flush, rescore pending transfers.
          </p>
          <Link href="/" className="btn-tertiary">
            ← Back to LandGuard
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-citizen px-6 py-10">
      <DemoControlPanel />
    </main>
  );
}
