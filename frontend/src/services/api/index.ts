import axios from "axios";
import cookie from "js-cookie";
import router from "@/plugins/router";
import { debounce } from "lodash";

const api = axios.create({ baseURL: "/api", timeout: 120000 });

const inflightRequests = new Set();

const networkQuiesced = debounce(() => {
  document.dispatchEvent(new CustomEvent("network-quiesced"));
}, 300);

// Set CSRF header for all requests
api.interceptors.request.use((config) => {
  inflightRequests.add(config.url);
  networkQuiesced.cancel();

  config.headers["x-csrftoken"] = cookie.get("csrftoken");
  return config;
});

api.interceptors.response.use(
  (response) => {
    inflightRequests.delete(response.config.url);

    // If there are no more inflight requests, fetch home data
    if (inflightRequests.size === 0) {
      networkQuiesced();
    }

    return response;
  },
  (error) => {
    if (error.response?.status === 403) {
      router.push({
        name: "login",
        params: { next: router.currentRoute.value.path },
      });
    }
    return Promise.reject(error);
  }
);

export default api
