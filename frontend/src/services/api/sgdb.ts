import type { SearchCoverSchema } from "@/__generated__";
import api from "@/services/api";

export const romApi = api;

async function searchCover({
  searchTerm,
}: {
  searchTerm: string;
}): Promise<{ data: SearchCoverSchema[] }> {
  return api.get("/search/cover", { params: { search_term: searchTerm } });
}

export default {
  searchCover,
};
