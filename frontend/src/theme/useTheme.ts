import { useCallback, useSyncExternalStore } from "react";
import {
  type ThemePreference,
  type ResolvedTheme,
  applyThemeAttribute,
  getStoredPreference,
  listenStorageChanges,
  listenSystemTheme,
  resolveTheme,
  setStoredPreference,
} from "./theme-storage";

let currentPref: ThemePreference = getStoredPreference();
let currentResolved: ResolvedTheme = resolveTheme(currentPref);
const listeners = new Set<() => void>();

function notify() {
  for (const fn of listeners) fn();
}

function updateResolved() {
  const newResolved = resolveTheme(currentPref);
  if (newResolved !== currentResolved) {
    currentResolved = newResolved;
    applyThemeAttribute(currentResolved);
    notify();
  }
}

// Listen for system theme changes (always, in case user switches to "system" later)
if (typeof window !== "undefined") {
  listenSystemTheme(() => {
    if (currentPref === "system") {
      updateResolved();
    }
  });

  listenStorageChanges((pref) => {
    currentPref = pref;
    updateResolved();
  });
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function getSnapshot(): ResolvedTheme {
  return currentResolved;
}

function getPreferenceSnapshot(): ThemePreference {
  return currentPref;
}

export function useTheme() {
  const resolved = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
  const preference = useSyncExternalStore(subscribe, getPreferenceSnapshot, getPreferenceSnapshot);

  const setTheme = useCallback((pref: ThemePreference) => {
    currentPref = pref;
    setStoredPreference(pref);
    updateResolved();
  }, []);

  const toggleTheme = useCallback(() => {
    const next: ThemePreference = resolved === "light" ? "dark" : "light";
    setTheme(next);
  }, [resolved, setTheme]);

  return {
    /** The currently resolved theme (always "light" or "dark") */
    resolved,
    /** The user's stored preference */
    preference,
    /** Set a specific theme preference */
    setTheme,
    /** Toggle between light and dark */
    toggleTheme,
    /** Whether the current resolved theme is dark */
    isDark: resolved === "dark",
  };
}
