/**
 * Theme storage — localStorage persistence and system preference detection.
 *
 * localStorage key: opspilot-theme
 * Values: "light" | "dark" | "system"
 */

const STORAGE_KEY = "opspilot-theme";

export type ThemePreference = "light" | "dark" | "system";
export type ResolvedTheme = "light" | "dark";

export function getStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    /* localStorage unavailable */
  }
  return "light";
}

export function setStoredPreference(pref: ThemePreference): void {
  try {
    localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    /* localStorage unavailable */
  }
}

export function getSystemPreference(): ResolvedTheme {
  if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export function resolveTheme(pref: ThemePreference): ResolvedTheme {
  if (pref === "system") {
    return getSystemPreference();
  }
  return pref;
}

export function applyThemeAttribute(theme: ResolvedTheme): void {
  const html = document.documentElement;
  if (theme === "dark") {
    html.setAttribute("data-theme", "dark");
  } else {
    html.removeAttribute("data-theme");
  }
  // Also update meta theme-color for browser chrome
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    meta.setAttribute("content", theme === "dark" ? "#161616" : "#f4f4f4");
  }
}

/**
 * Initialize theme before React renders (call in index.html inline script).
 * This prevents flash-of-wrong-theme.
 */
export function initTheme(): ResolvedTheme {
  const pref = getStoredPreference();
  const resolved = resolveTheme(pref);
  applyThemeAttribute(resolved);
  return resolved;
}

/**
 * Listen for system theme changes (for "system" preference).
 * Returns an unsubscribe function.
 */
export function listenSystemTheme(onChange: (theme: ResolvedTheme) => void): () => void {
  const mq = window.matchMedia("(prefers-color-scheme: dark)");
  const handler = (e: MediaQueryListEvent) => {
    onChange(e.matches ? "dark" : "light");
  };
  mq.addEventListener("change", handler);
  return () => mq.removeEventListener("change", handler);
}

/**
 * Sync theme across tabs via storage event.
 */
export function listenStorageChanges(onChange: (pref: ThemePreference) => void): () => void {
  const handler = (e: StorageEvent) => {
    if (e.key === STORAGE_KEY) {
      const val = e.newValue as ThemePreference | null;
      if (val === "light" || val === "dark" || val === "system") {
        onChange(val);
      }
    }
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}
