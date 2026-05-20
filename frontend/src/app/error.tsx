"use client";

import { RefreshCw, ShieldAlert } from "lucide-react";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="card-elevated w-full max-w-md space-y-4">
        <div className="flex items-start gap-3">
          <span className="rounded-md bg-status-frozen/10 p-2 text-status-frozen">
            <ShieldAlert className="size-5" aria-hidden />
          </span>
          <div className="flex-1">
            <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
              Unexpected error
            </p>
            <h1 className="font-serif text-lg font-semibold text-slate-900">
              Something went wrong
            </h1>
          </div>
        </div>
        <p className="text-sm text-slate-700">
          {error.message || "An unexpected error occurred."}
        </p>
        {error.digest && (
          <p className="font-mono text-xs text-slate-500">
            digest: {error.digest}
          </p>
        )}
        <button
          onClick={reset}
          className="btn-primary w-full justify-center"
          type="button"
        >
          <RefreshCw className="size-4" />
          <span>Try again</span>
        </button>
      </div>
    </main>
  );
}
