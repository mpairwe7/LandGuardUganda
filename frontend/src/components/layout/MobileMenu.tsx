"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Menu, X } from "lucide-react";

interface Props {
  /** Accessible name for the trigger button + dialog (e.g. "Open menu"). */
  triggerLabel: string;
  /** Slot above the close button in the panel header (e.g. brand). */
  headerSlot?: React.ReactNode;
  /** Body of the drawer — usually a nav list. */
  children: React.ReactNode;
  /** Optional extra class on the trigger (defaults to a quiet icon button). */
  triggerClassName?: string;
  /** Optional `aria-label` for the trigger if you want different copy. */
  triggerAriaLabel?: string;
  /** Side the panel slides in from. Defaults to "left". */
  side?: "left" | "right";
}

/**
 * Slide-in panel for compact viewports. Body-scroll-locked while open,
 * dismisses on Esc, on backdrop tap, and on any link click inside the
 * panel (the children own their own onClick chain — we just snapshot
 * the click bubble through `onClick={close}` at the panel root).
 *
 * Visibility is controlled here; the parent decides where to render
 * it. We deliberately don't wrap in a portal — Tailwind `fixed` with
 * a high z-index is sufficient and keeps SSR simple.
 */
export function MobileMenu({
  triggerLabel,
  headerSlot,
  children,
  triggerClassName,
  triggerAriaLabel,
  side = "left",
}: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const closeBtnRef = useRef<HTMLButtonElement | null>(null);

  // Lock body scroll while open + return scroll position on close.
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Esc to close + initial focus to the close button (so screen reader
  // users land somewhere predictable).
  useEffect(() => {
    if (!open) return;
    closeBtnRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const close = () => setOpen(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={triggerAriaLabel ?? triggerLabel}
        aria-expanded={open}
        aria-controls={panelId}
        className={
          triggerClassName ??
          "inline-flex size-9 items-center justify-center rounded-md text-current hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-guard-600 focus-visible:ring-offset-2"
        }
      >
        <Menu className="size-5" aria-hidden />
      </button>

      {/* The drawer renders unconditionally so transitions can animate
          smoothly. `pointer-events-none` + opacity-0 hides it when
          closed; we don't return null so the trigger's aria-controls
          can resolve to a real element. */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={triggerLabel}
        id={panelId}
        className={`fixed inset-0 z-50 ${
          open ? "pointer-events-auto" : "pointer-events-none"
        }`}
      >
        {/* Backdrop */}
        <div
          aria-hidden
          onClick={close}
          className={`absolute inset-0 bg-slate-950/60 transition-opacity ${
            open ? "opacity-100" : "opacity-0"
          }`}
        />
        {/* Panel */}
        <div
          onClick={(e) => {
            // Auto-close on link clicks; let everything else handle itself.
            const target = e.target as HTMLElement;
            if (target.closest("a")) close();
          }}
          className={`absolute inset-y-0 flex w-[min(20rem,85vw)] flex-col bg-white shadow-elevated transition-transform duration-200 ${
            side === "left"
              ? `left-0 ${open ? "translate-x-0" : "-translate-x-full"}`
              : `right-0 ${open ? "translate-x-0" : "translate-x-full"}`
          }`}
        >
          <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
            <div className="min-w-0 flex-1">{headerSlot}</div>
            <button
              ref={closeBtnRef}
              type="button"
              onClick={close}
              aria-label="Close menu"
              className="inline-flex size-9 shrink-0 items-center justify-center rounded-md text-slate-700 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-guard-600 focus-visible:ring-offset-2"
            >
              <X className="size-5" aria-hidden />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-4 py-4">{children}</div>
        </div>
      </div>
    </>
  );
}
