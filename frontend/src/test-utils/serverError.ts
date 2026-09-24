import { AxiosError } from "axios";

/** A refused request as axios rejects it, carrying FastAPI's `detail`. */
export function serverError(detail: string, status = 503): AxiosError {
  return Object.assign(new AxiosError(`HTTP ${status}`), {
    response: { status, data: { detail } },
  });
}
