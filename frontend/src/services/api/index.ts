import axios from "axios";
import { default as Cookies } from "js-cookie";
import { debounce } from "lodash";
import router from "@/plugins/router";
import { ROUTES } from "@/plugins/router";

const api = axios.create({
  // This will keep the url query params on refresh
  baseURL: "/api",
  timeout: 120000,
  paramsSerializer: {
    serialize: (params) => {
      const searchParams = new URLSearchParams();

      Object.keys(params).forEach((key) => {
        const value = params[key];
        if (Array.isArray(value)) {
          // Handle arrays by repeating the parameter name (not adding [])
          value.forEach((item) => {
            if (item !== undefined && item !== null) {
              searchParams.append(key, String(item));
            }
          });
        } else if (value !== undefined && value !== null) {
          searchParams.append(key, String(value));
        }
      });

      return searchParams.toString();
    },
  },
});

const inflightRequests = new Set();

const networkQuiesced = debounce(() => {
  document.dispatchEvent(new CustomEvent("network-quiesced"));
}, 250);

api.interceptors.request.use((config) => {
  // Add request to set of inflight requests
  inflightRequests.add(config.url);

  // Cancel debounced networkQuiesced since a new request just came in
  networkQuiesced.cancel();

  // Set CSRF header for all requests
  config.headers["x-csrftoken"] = Cookies.get("romm_csrftoken");
  return config;
});

api.interceptors.response.use(
  (response) => {
    // Remove request from set of inflight requests
    inflightRequests.delete(response.config.url);

    // If there are no more inflight requests, fetch app-wide data
    if (inflightRequests.size === 0) {
      networkQuiesced();
    }

    return response;
  },
  async (error) => {
    if (error.response?.status === 403) {
      // Clear cookies and redirect to login page
      Cookies.remove("romm_session");

      // Refetch CSRF cookie
      await refetchCSRFToken();

      const pathname = window.location.pathname;
      const params = new URLSearchParams(window.location.search);

      router.push({
        name: ROUTES.LOGIN,
        query: {
          next: params.get("next") ?? (pathname !== "/login" ? pathname : "/"),
        },
      });
    }
    return Promise.reject(error);
  },
);

export default api;

export async function refetchCSRFToken() {
  Cookies.remove("romm_csrftoken");

  return await api.get("/heartbeat");
}
