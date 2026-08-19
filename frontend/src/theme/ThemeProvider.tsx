import { type ReactNode } from "react";
import { initTheme } from "./theme-storage";

/**
 * ThemeProvider — applies the initial theme attribute to <html> before
 * the first React render, preventing flash-of-wrong-theme.
 *
 * The `useTheme` hook is the primary API for consuming theme state;
 * this provider exists for structural clarity and future extensibility.
 */

// Initialize synchronously on module load (before React hydration)
initTheme();

export function ThemeProvider({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
