"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Power, PowerOff, Anchor, RefreshCw, Activity } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { Button } from "@/components/common/Button";
import { StatusPill } from "@/components/common/StatusPill";

interface DemoStatus {
  demo_mode: boolean;
  anchor_breaker: string;
  nira_breaker: string;
}

/**
 * The showcase orchestration surface. Act 5 ("resilience under chain
 * outage") runs through this panel. The presenter is operating live on
 * stage, so every action is a single click, every result is one of two
 * unambiguous states, and the breaker pills update without a refresh.
 */
export function DemoControlPanel() {
  const status = useQuery({
    queryKey: ["demo", "status"],
    queryFn: () => api.get<DemoStatus>("/v1/demo/status"),
    refetchInterval: 4_000,
  });

  const rpcKill = useDemoAction("/v1/demo/rpc-kill", "Blockchain RPC killed — anchors will queue.", status.refetch);
  const rpcRestore = useDemoAction("/v1/demo/rpc-restore", "Blockchain RPC restored — draining queue.", status.refetch);
  const niraKill = useDemoAction("/v1/demo/nira-kill", "NIRA killed — KYC will fall back to cache.", status.refetch);
  const niraRestore = useDemoAction("/v1/demo/nira-restore", "NIRA restored.", status.refetch);
  const flush3 = useDemoAction("/v1/demo/flush-anchor/3", "Mityana anchor flush triggered.", status.refetch);
  const rescore = useDemoAction("/v1/demo/rescore-pending", "Rescoring pending transfers…", status.refetch);

  return (
    <div className="space-y-6">
      <header className="border-b border-slate-200 pb-4">
        <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
          Showcase orchestration
        </p>
        <h1 className="font-serif text-2xl font-bold text-slate-900">
          Demo Control Panel
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-600">
          Orchestrate the 25 June 2026 storyboard. Every action here has a
          backup manual procedure in{" "}
          <code className="font-mono text-slate-800">DEMO_RUNBOOK.md</code>.
        </p>
      </header>

      {/* LIVE BREAKER STATE -------------------------------------------- */}
      <section className="card-elevated">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-2">
            <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
              Live breaker state
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <BreakerPill label="Anchor" value={status.data?.anchor_breaker} />
              <BreakerPill label="NIRA" value={status.data?.nira_breaker} />
            </div>
          </div>
          <Activity
            className={`size-7 ${status.isFetching ? "animate-pulse text-guard-700" : "text-slate-400"}`}
            aria-hidden
          />
        </div>
      </section>

      {/* ACTIONS -------------------------------------------------------- */}
      <section className="grid gap-4 sm:grid-cols-2">
        <ActCard
          act="Act 5"
          title="Kill the blockchain"
          body="Forces the anchor circuit breaker open. New titles still issue; their anchors queue."
        >
          <Button
            variant="destructive"
            size="sm"
            icon={<PowerOff className="size-4" />}
            onClick={() => rpcKill.mutate()}
            loading={rpcKill.isPending}
          >
            Kill RPC
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<Power className="size-4" />}
            onClick={() => rpcRestore.mutate()}
            loading={rpcRestore.isPending}
          >
            Restore RPC
          </Button>
        </ActCard>

        <ActCard
          act="Backup"
          title="NIRA failure modes"
          body="Demonstrates graceful degradation: cached KYC continues to serve."
        >
          <Button
            variant="destructive"
            size="sm"
            icon={<PowerOff className="size-4" />}
            onClick={() => niraKill.mutate()}
            loading={niraKill.isPending}
          >
            Kill NIRA
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<Power className="size-4" />}
            onClick={() => niraRestore.mutate()}
            loading={niraRestore.isPending}
          >
            Restore NIRA
          </Button>
        </ActCard>

        <ActCard
          act="Acts 2, 5"
          title="Anchor management"
          body="Force Mityana's pending events to anchor immediately. Used to pre-warm the timeline."
        >
          <Button
            variant="primary"
            size="sm"
            icon={<Anchor className="size-4" />}
            onClick={() => flush3.mutate()}
            loading={flush3.isPending}
          >
            Flush Mityana now
          </Button>
        </ActCard>

        <ActCard
          act="Act 3"
          title="Fraud queue"
          body="Replays the scorer over pending transfers. Useful if the fraud worker was paused."
        >
          <Button
            variant="primary"
            size="sm"
            icon={<RefreshCw className="size-4" />}
            onClick={() => rescore.mutate()}
            loading={rescore.isPending}
          >
            Rescore pending
          </Button>
        </ActCard>
      </section>

      <p className="border-l-2 border-status-pending bg-status-pending/5 pl-4 py-2 text-xs leading-relaxed text-slate-600">
        <strong className="text-slate-900">Stage note:</strong> for Act 5, kill
        the RPC, issue one title in the registrar console (it shows{" "}
        <em>Anchor pending</em>), then restore + flush. The pending badge flips
        green and the new tx appears in the anchor explorer within ~3 seconds.
      </p>
    </div>
  );
}

function useDemoAction(path: string, success: string, after: () => void) {
  return useMutation({
    mutationFn: () => api.post<unknown>(path),
    onSuccess: () => {
      toast.success(success);
      after();
    },
    onError: (err) =>
      toast.error(`Failed: ${(err as { detail?: string }).detail ?? "see logs"}`),
  });
}

function BreakerPill({ label, value }: { label: string; value?: string }) {
  if (!value) return <StatusPill kind="neutral">{label}: —</StatusPill>;
  const kind =
    value === "open" ? "pending" : value === "closed" ? "verified" : "neutral";
  return (
    <StatusPill kind={kind}>
      {label}: {value}
    </StatusPill>
  );
}

function ActCard({
  act,
  title,
  body,
  children,
}: {
  act: string;
  title: string;
  body: string;
  children: React.ReactNode;
}) {
  return (
    <div className="card-surface space-y-3">
      <header>
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-seal-700">
          {act}
        </p>
        <h3 className="font-serif text-base font-semibold text-slate-900">
          {title}
        </h3>
        <p className="mt-1 text-xs text-slate-600">{body}</p>
      </header>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}
