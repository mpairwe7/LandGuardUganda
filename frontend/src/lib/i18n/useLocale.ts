// Tiny client-side i18n hook. Persists the chosen locale in a cookie
// (`lg_locale`) so SSR and client agree on first paint after the
// initial hydration. No external i18n library — the catalogue is
// small enough that React state + Object lookup is the right scope.

"use client";

import { useCallback, useEffect, useState } from "react";
import { DEFAULT_LOCALE, LOCALES, type Locale, type Messages, messages } from "./messages";

const COOKIE_NAME = "lg_locale";

function readLocaleFromCookie(): Locale {
  if (typeof document === "undefined") return DEFAULT_LOCALE;
  const match = document.cookie.match(
    new RegExp("(?:^|; )" + COOKIE_NAME + "=([^;]*)"),
  );
  const v = match?.[1];
  return (LOCALES as readonly string[]).includes(v ?? "")
    ? (v as Locale)
    : DEFAULT_LOCALE;
}

export function useLocale(): {
  locale: Locale;
  setLocale: (loc: Locale) => void;
  t: (key: keyof Messages) => string;
} {
  // Hydrate from the default first so SSR + the very first client
  // render agree, then sync from cookie immediately afterwards.
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    setLocaleState(readLocaleFromCookie());
  }, []);

  const setLocale = useCallback((loc: Locale) => {
    setLocaleState(loc);
    if (typeof document !== "undefined") {
      // 1 year — locale preference is sticky.
      document.cookie = `${COOKIE_NAME}=${loc}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
    }
  }, []);

  const t = useCallback(
    (key: keyof Messages): string => messages[locale][key] ?? messages.en[key],
    [locale],
  );

  return { locale, setLocale, t };
}
