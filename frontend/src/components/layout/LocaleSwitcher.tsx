"use client";

import { useLocale } from "@/lib/i18n/useLocale";
import { LOCALES, LOCALE_LABEL, type Locale } from "@/lib/i18n/messages";
import { Languages } from "lucide-react";

/**
 * Minimal locale picker shown in the public layout header. Wired to the
 * `lg_locale` cookie via useLocale. Re-renders any subscribed component
 * (verifier page) when the locale changes.
 */
export function LocaleSwitcher() {
  const { locale, setLocale, t } = useLocale();
  return (
    <label className="flex items-center gap-1 text-xs text-slate-600">
      <Languages className="size-3.5 text-slate-500" aria-hidden />
      <span className="sr-only">{t("locale.switch_to")}</span>
      <select
        aria-label={t("locale.switch_to")}
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        className="rounded-md border border-slate-200 bg-white py-0.5 pl-1.5 pr-6 text-xs text-slate-800 focus:border-guard-400 focus:outline-none focus:ring-1 focus:ring-guard-400"
      >
        {LOCALES.map((l) => (
          <option key={l} value={l}>
            {LOCALE_LABEL[l]}
          </option>
        ))}
      </select>
    </label>
  );
}
