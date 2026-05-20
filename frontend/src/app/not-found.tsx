import Link from "next/link";
import { ArrowLeft, MapPinned } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6">
      <div className="card-elevated w-full max-w-md space-y-4 text-center">
        <div className="mx-auto flex size-12 items-center justify-center rounded-full bg-slate-100 text-slate-500">
          <MapPinned className="size-6" aria-hidden />
        </div>
        <div className="space-y-1">
          <p className="text-caption uppercase tracking-[0.16em] text-slate-500">
            Error 404
          </p>
          <h1 className="font-serif text-2xl font-bold text-slate-900">
            Page not found
          </h1>
          <p className="text-sm text-slate-600">
            The land record you&apos;re looking for has moved — or never
            existed.
          </p>
        </div>
        <div className="pt-2">
          <Link href="/" className="btn-primary inline-flex">
            <ArrowLeft className="size-4" />
            <span>Back to LandGuard</span>
          </Link>
        </div>
      </div>
    </main>
  );
}
