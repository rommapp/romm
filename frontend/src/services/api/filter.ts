import api from "@/services/api/index";

export const stateApi = api;

async function getFilters(): Promise<{ data: { genres: string[] } }> {
  return api.get("/filters");
}
export default {
  getFilters,
};
