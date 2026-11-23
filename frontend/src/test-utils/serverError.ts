import { AxiosError } from "axios";

/** A refused request as axios rejects it, with `data` as the response body. */
export function responseError(status: number, data: unknown): AxiosError {
  return Object.assign(new AxiosError(`HTTP ${status}`), {
    response: { status, data },
  });
}

/** A refused request as axios rejects it, carrying FastAPI's `detail`. */
export function serverError(detail: unknown, status = 503): AxiosError {
  return responseError(status, { detail });
}
