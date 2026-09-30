// Schemes that would run or load content in this page instead of handing off to an app.
const BLOCKED_SCHEMES = new Set([
  "http:",
  "https:",
  "javascript:",
  "data:",
  "vbscript:",
  "blob:",
  "filesystem:",
  "file:",
]);

/** Whether a pairing callback targets a native app's custom URL scheme. */
export function isCustomScheme(url: string): boolean {
  try {
    return !BLOCKED_SCHEMES.has(new URL(url).protocol);
  } catch {
    return false;
  }
}
