import { AxiosError } from "axios";
import type {
  AxiosAdapter,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from "axios";
import api from "@/services/api";

type Method = "get" | "post" | "put" | "patch" | "delete";

export interface MockRoute {
  method?: Method;
  /** A string matches the request path exactly; a RegExp tests it. */
  url: string | RegExp;
  status?: number;
  data?: unknown | ((config: InternalAxiosRequestConfig) => unknown);
  /** Never settles, to hold a component in its loading state. */
  pending?: boolean;
}

/** Answers requests on the shared `api` client from `routes` until the
 *  returned cleanup runs. An unmatched request fails with 404, so a missing
 *  mock shows up as the component's own error state.
 */
export function mockApi(routes: MockRoute[]): () => void {
  const original = api.defaults.adapter;

  const adapter: AxiosAdapter = (config) => {
    const method = (config.method ?? "get").toLowerCase();
    const path = config.url ?? "";
    const route = routes.find(
      (r) =>
        (r.method ?? "get") === method &&
        (typeof r.url === "string" ? r.url === path : r.url.test(path)),
    );
    if (route?.pending) return new Promise(() => {});

    const status = route ? (route.status ?? 200) : 404;
    const data = !route
      ? { detail: `No mock for ${method.toUpperCase()} ${path}` }
      : typeof route.data === "function"
        ? route.data(config)
        : route.data;
    const response: AxiosResponse = {
      data,
      status,
      statusText: "",
      headers: {},
      config,
    };
    if (status < 400) return Promise.resolve(response);
    return Promise.reject(
      new AxiosError(
        `Request failed with status code ${status}`,
        String(status),
        config,
        null,
        response,
      ),
    );
  };

  api.defaults.adapter = adapter;
  return () => {
    api.defaults.adapter = original;
  };
}
