// FastAPI puts the useful text in `response.data.detail`; axios' own
// `message` is a generic "Request failed with status code N".
import axios from "axios";

export function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    return err.message;
  }
  return err instanceof Error ? err.message : String(err);
}
