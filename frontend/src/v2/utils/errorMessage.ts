// FastAPI puts the useful text in `response.data.detail`; axios' own
// `message` is a generic "Request failed with status code N".
import axios from "axios";

/** `fallback`, when given, stands in for anything but the server's own detail. */
export function errorMessage(err: unknown, fallback?: string): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    return fallback ?? err.message;
  }
  return fallback ?? (err instanceof Error ? err.message : String(err));
}
