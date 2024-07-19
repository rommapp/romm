import router from "@/plugins/router";
import axios from "axios";
import { default as cookie, default as Cookies } from "js-cookie";
import { debounce } from "lodash";

const api = axios.create({ baseURL: "/api", timeout: 120000 });

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
  config.headers["x-csrftoken"] = cookie.get("csrftoken");
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
  (error) => {
    if (error.response?.status === 403) {
      const allCookies = Cookies.get(); // Get all cookies
      for (const cookie in allCookies) {
        Cookies.remove(cookie); // Remove each cookie
      }
      router.push({
        name: "login",
        query: { next: router.currentRoute.value.path },
      });
    }
    return Promise.reject(error);
  },
);

export default api;
