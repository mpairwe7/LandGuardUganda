// Hook over the shared useLocaleStore (Zustand). State is global so the
// LocaleSwitcher in the header and any t()-using page see the same value.
//
// First paint: SSR + initial client render use DEFAULT_LOCALE so they
// agree. `hydrateFromCookie` runs once in a top-level effect (handled by
// LocaleSwitcher's mount) and re-renders the whole tree with the user's
// stored preference.

"use client";

import { useCallback, useEffect } from "react";
import { type Locale, type Messages, messages } from "./messages";
import { useLocaleStore } from "@/store/useLocaleStore";

export function useLocale(): {
  locale: Locale;
  setLocale: (loc: Locale) => void;
  t: (key: keyof Messages) => string;
} {
  const locale = useLocaleStore((s) => s.locale);
  const setLocale = useLocaleStore((s) => s.setLocale);
  const hydrated = useLocaleStore((s) => s.hydrated);
  const hydrateFromCookie = useLocaleStore((s) => s.hydrateFromCookie);

  useEffect(() => {
    if (!hydrated) hydrateFromCookie();
  }, [hydrated, hydrateFromCookie]);

  const t = useCallback(
    (key: keyof Messages): string => messages[locale][key] ?? messages.en[key],
    [locale],
  );

  return { locale, setLocale, t };
}
