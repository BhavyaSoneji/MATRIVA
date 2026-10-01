export type Lang = "en" | "hi" | "gu";

export const LANGS: { id: Lang; label: string; speech: string; name: string }[] = [
  { id: "en", label: "EN", speech: "en-IN", name: "English" },
  { id: "hi", label: "हिं", speech: "hi-IN", name: "Hindi" },
  { id: "gu", label: "ગુ", speech: "gu-IN", name: "Gujarati" },
];

const KEY = "matriva.lang";

export function loadLang(): Lang {
  try {
    const v = window.localStorage.getItem(KEY);
    if (v === "en" || v === "hi" || v === "gu") return v;
  } catch {
    // storage unavailable -- fall back to English
  }
  return "en";
}

export function saveLang(lang: Lang) {
  try {
    window.localStorage.setItem(KEY, lang);
  } catch {
    // ignore storage errors
  }
}

export function speechLocale(lang: Lang): string {
  return LANGS.find((l) => l.id === lang)?.speech ?? "en-IN";
}
