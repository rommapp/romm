// Shared types + helpers for the MatchRom body variants (grid /
// list). The dialog shell owns search state and API calls; each body
// variant renders results + the per-match cover / rename picker in
// its own visual language.
import type { SearchRom } from "@/stores/roms";
import { providerImageUrl } from "@/utils/providerImage";

export type SourceName =
  | "IGDB"
  | "Mobygames"
  | "Screenscraper"
  | "Flashpoint"
  | "Launchbox"
  | "Libretro"
  | "Steam"
  | "SteamGridDB";

export interface MatchedSource {
  url_cover: string;
  /** Same-origin `url_cover` for display; `url_cover` is what gets saved. */
  preview_url: string;
  name: SourceName;
  logo_path: string;
}

interface SourceDef {
  urlKey: keyof SearchRom;
  name: SourceName;
  logo: string;
}

const SOURCE_DEFS: readonly SourceDef[] = [
  {
    urlKey: "igdb_url_cover",
    name: "IGDB",
    logo: "/assets/scrappers/igdb.png",
  },
  {
    urlKey: "moby_url_cover",
    name: "Mobygames",
    logo: "/assets/scrappers/moby.png",
  },
  {
    urlKey: "ss_url_cover",
    name: "Screenscraper",
    logo: "/assets/scrappers/ss.png",
  },
  {
    urlKey: "sgdb_url_cover",
    name: "SteamGridDB",
    logo: "/assets/scrappers/sgdb.png",
  },
  {
    urlKey: "flashpoint_url_cover",
    name: "Flashpoint",
    logo: "/assets/scrappers/flashpoint.png",
  },
  {
    urlKey: "launchbox_url_cover",
    name: "Launchbox",
    logo: "/assets/scrappers/launchbox.png",
  },
  {
    urlKey: "libretro_url_cover",
    name: "Libretro",
    logo: "/assets/scrappers/libretro.png",
  },
  {
    urlKey: "steam_url_cover",
    name: "Steam",
    logo: "/assets/scrappers/steam.png",
  },
];

export function sourceLogo(name: SourceName): string {
  return SOURCE_DEFS.find((def) => def.name === name)?.logo ?? "";
}

export function getMatchSources(matchedRom: SearchRom): MatchedSource[] {
  const out: MatchedSource[] = [];
  for (const def of SOURCE_DEFS) {
    const url = matchedRom[def.urlKey] as string | undefined | null;
    if (url) {
      out.push({
        url_cover: url,
        preview_url: providerImageUrl(url),
        name: def.name,
        logo_path: def.logo,
      });
    }
  }
  return out;
}

export function matchKey(rom: SearchRom): string {
  return `${rom.igdb_id ?? "_"}-${rom.moby_id ?? "_"}-${rom.ss_id ?? "_"}-${rom.name}`;
}

// Preview URL (same-origin) of a search result's first provider cover, for
// GameCard's `cover-src`, since SearchRom has no `path_cover_*`. Absent
// providers come back as "", hence the truthy filter rather than `??`.
export function firstAvailableCover(r: SearchRom): string | null {
  const candidates: Array<string | undefined> = [
    r.igdb_url_cover,
    r.moby_url_cover,
    r.ss_url_cover,
    r.sgdb_url_cover,
    r.flashpoint_url_cover,
    r.launchbox_url_cover,
    r.libretro_url_cover,
    r.steam_url_cover,
  ];
  const cover = candidates.find((c): c is string => Boolean(c));
  return cover ? providerImageUrl(cover) : null;
}

export interface ConfirmPayload {
  matchedRom: SearchRom;
  cover: MatchedSource | undefined;
  renameFromSource: boolean;
}

export type MatchVariant = "list" | "grid";
