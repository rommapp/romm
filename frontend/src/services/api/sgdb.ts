import type { SearchCoverSchema } from "@/__generated__";
import api from "@/services/api";

export const romApi = api;

async function searchCover({ searchTerm }: { searchTerm: string }) {
  return api.get<SearchCoverSchema[]>("/search/cover", {
    params: { search_term: searchTerm },
  });
}

export default {
  searchCover,
};
