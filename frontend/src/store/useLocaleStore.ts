"use client";

import { create } from "zustand";
import { DEFAULT_LOCALE, LOCALES, type Locale } from "@/lib/i18n/messages";

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

function writeCookie(loc: Locale) {
  if (typeof document === "undefined") return;
  // 1 year. SameSite=Lax so links from other origins still pick up the
  // preference (the cookie is non-sensitive — language only).
  document.cookie = `${COOKIE_NAME}=${loc}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
}

interface LocaleState {
  locale: Locale;
  hydrated: boolean;
  setLocale: (loc: Locale) => void;
  hydrateFromCookie: () => void;
}

export const useLocaleStore = create<LocaleState>((set) => ({
  locale: DEFAULT_LOCALE,
  hydrated: false,
  setLocale: (locale) => {
    writeCookie(locale);
    set({ locale });
  },
  hydrateFromCookie: () => {
    set({ locale: readLocaleFromCookie(), hydrated: true });
  },
}));
