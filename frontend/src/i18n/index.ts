import { createI18n } from "vue-i18n";

import en from "@/locales/en.json";
import ja from "@/locales/ja.json";
import zh from "@/locales/zh.json";

export type LocaleCode = "zh-CN" | "ja-JP" | "en-US";

export const SUPPORTED_LOCALES: Array<{ value: LocaleCode; label: string }> = [
  { value: "zh-CN", label: "中文" },
  { value: "ja-JP", label: "日本語" },
  { value: "en-US", label: "English" }
];

export const DEFAULT_LOCALE: LocaleCode = "zh-CN";
const STORAGE_KEY = "kabucount-locale";

function getStoredLocale(): LocaleCode | null {
  if (typeof window === "undefined") {
    return null;
  }
  const saved = window.localStorage.getItem(STORAGE_KEY) as LocaleCode | null;
  return saved && SUPPORTED_LOCALES.some((item) => item.value === saved) ? saved : null;
}

function getBrowserLocale(): LocaleCode | null {
  if (typeof navigator === "undefined") {
    return null;
  }
  const locales = [navigator.language, ...(navigator.languages ?? [])];
  const match = locales.find((code) => SUPPORTED_LOCALES.some((item) => item.value === code));
  return (match as LocaleCode | undefined) ?? null;
}

const initialLocale: LocaleCode = getStoredLocale() ?? getBrowserLocale() ?? DEFAULT_LOCALE;

export const i18n = createI18n({
  legacy: false,
  locale: initialLocale,
  fallbackLocale: "en-US",
  messages: {
    "zh-CN": zh,
    "ja-JP": ja,
    "en-US": en
  }
});

export function setLocale(locale: LocaleCode) {
  i18n.global.locale.value = locale;
  if (typeof window !== "undefined") {
    window.localStorage.setItem(STORAGE_KEY, locale);
  }
}

export function getCurrentLocale(): LocaleCode {
  return i18n.global.locale.value as LocaleCode;
}

export default i18n;
