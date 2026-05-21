// Shared types + helpers for the three MatchRom body variants
// (Drawer / Split / Spotlight). The dialog shell owns search state and
// API calls; each body variant renders results + the per-match cover/
// rename picker in its own visual language.
import type { SearchRom } from "@/stores/roms";

export type SourceName =
  | "IGDB"
  | "Mobygames"
  | "Screenscraper"
  | "Flashpoint"
  | "Launchbox"
  | "Libretro"
  | "SteamGridDB";

export interface MatchedSource {
  url_cover: string;
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
];

export function getMatchSources(matchedRom: SearchRom): MatchedSource[] {
  const out: MatchedSource[] = [];
  for (const def of SOURCE_DEFS) {
    const url = matchedRom[def.urlKey] as string | undefined | null;
    if (url) {
      out.push({ url_cover: url, name: def.name, logo_path: def.logo });
    }
  }
  return out;
}

export function matchKey(rom: SearchRom): string {
  return `${rom.igdb_id ?? "_"}-${rom.moby_id ?? "_"}-${rom.ss_id ?? "_"}-${rom.name}`;
}

// Default cover URL for a search result — used when rendering the
// match as a card. SearchRom carries only `*_url_cover` per provider
// (no `path_cover_*` / `url_cover` like SimpleRom), so cards fed to
// GameCard need `cover-src` set explicitly. First available provider
// cover wins; null means no provider has a cover at all (placeholder).
// Uses a truthy filter (not `??`) because the backend sometimes returns
// empty strings for absent providers — `??` would treat "" as "present"
// and short-circuit before reaching the actually-populated provider.
export function firstAvailableCover(r: SearchRom): string | null {
  const candidates: Array<string | undefined> = [
    r.igdb_url_cover,
    r.moby_url_cover,
    r.ss_url_cover,
    r.sgdb_url_cover,
    r.flashpoint_url_cover,
    r.launchbox_url_cover,
    r.libretro_url_cover,
  ];
  return candidates.find((c): c is string => Boolean(c)) ?? null;
}

export interface ConfirmPayload {
  matchedRom: SearchRom;
  cover: MatchedSource | undefined;
  renameFromSource: boolean;
}

export type MatchVariant = "split" | "spotlight";
