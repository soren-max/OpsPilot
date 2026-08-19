const ENVIRONMENT_KEY = "opspilot-environment";

export function readEnvironmentPreference(): string {
  try {
    return localStorage.getItem(ENVIRONMENT_KEY) ?? "";
  } catch {
    return "";
  }
}

export function writeEnvironmentPreference(environmentId: string): void {
  try {
    localStorage.setItem(ENVIRONMENT_KEY, environmentId);
  } catch {
    // Hardened browsers may block storage. The in-memory selection remains usable.
  }
}
