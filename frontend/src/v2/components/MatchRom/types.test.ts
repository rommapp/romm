import { describe, expect, it } from "vitest";
import type { SearchRom } from "@/stores/roms";
import { firstAvailableCover, getMatchSources } from "./types";

const IGDB = "https://images.igdb.com/igdb/image/upload/t_cover_big/co1.jpg";
const PROXIED_IGDB = `/api/search/image?url=${encodeURIComponent(IGDB)}`;

function searchRom(overrides: Partial<SearchRom>): SearchRom {
  return {
    platform_id: 1,
    name: "Sonic",
    is_identified: true,
    is_unidentified: false,
    ...overrides,
  } as SearchRom;
}

describe("match cover previews", () => {
  it("previews sources through the proxy but saves the provider URL", () => {
    const [source] = getMatchSources(searchRom({ igdb_url_cover: IGDB }));

    expect(source.url_cover).toBe(IGDB);
    expect(source.preview_url).toBe(PROXIED_IGDB);
  });

  it("proxies the first populated provider cover", () => {
    expect(
      firstAvailableCover(
        searchRom({ moby_url_cover: "", igdb_url_cover: IGDB }),
      ),
    ).toBe(PROXIED_IGDB);
    expect(firstAvailableCover(searchRom({ igdb_url_cover: "" }))).toBeNull();
  });
});
