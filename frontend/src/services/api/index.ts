import router from "@/plugins/router";

import axios from "axios";

const api = axios.create({ baseURL: "/api", timeout: 120000 });

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response.status === 403) {
      router.push({
        name: "login",
        params: { next: router.currentRoute.value.path },
      });
    }
    return Promise.reject(error);
  }
);

export default api
