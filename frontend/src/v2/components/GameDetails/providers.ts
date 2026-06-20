// Metadata-provider registry. Single source of truth for the provider
// list rendered by ProviderGrid (and any future surface that needs
// per-ROM provider links). Each entry binds a DetailedRom field to a
// brand colour token + logo + URL builder.
import type { DetailedRom } from "@/stores/roms";

export type Provider = {
  /** Field on DetailedRom that holds the provider's external ID. */
  key: keyof DetailedRom;
  name: string;
  /** CSS color value (token reference) — kept inline because tokens
   *  resolve at the consumer's CSS context, not at this file. */
  color: string;
  /** Optional favicon for the provider's identity. */
  logo: string | null;
  /** Optional URL builder; when null the card renders unlinked. */
  url: ((id: string | number) => string) | null;
};

export const PROVIDERS: Provider[] = [
  {
    key: "igdb_id",
    name: "IGDB",
    color: "var(--r-color-provider-igdb)",
    logo: "/assets/scrappers/igdb.png",
    url: (id) => `https://www.igdb.com/search?type=1&q=${id}`,
  },
  {
    key: "moby_id",
    name: "MobyGames",
    color: "var(--r-color-provider-moby)",
    logo: "/assets/scrappers/moby.png",
    url: (id) => `https://www.mobygames.com/game/${id}/`,
  },
  {
    key: "ss_id",
    name: "ScreenScraper",
    color: "var(--r-color-provider-screenscraper)",
    logo: "/assets/scrappers/ss.png",
    url: (id) => `https://www.screenscraper.fr/gameinfos.php?gameid=${id}`,
  },
  {
    key: "ra_id",
    name: "RetroAchievements",
    color: "var(--r-color-provider-retroachievements)",
    logo: "/assets/scrappers/ra.png",
    url: (id) => `https://retroachievements.org/game/${id}`,
  },
  {
    key: "sgdb_id",
    name: "SteamGridDB",
    color: "var(--r-color-provider-steamgriddb)",
    logo: "/assets/scrappers/sgdb.png",
    url: (id) => `https://www.steamgriddb.com/game/${id}`,
  },
  {
    key: "launchbox_id",
    name: "LaunchBox",
    color: "var(--r-color-provider-launchbox)",
    logo: "/assets/scrappers/launchbox.png",
    url: (id) => `https://gamesdb.launchbox-app.com/games/dbid/${id}`,
  },
  {
    key: "hasheous_id",
    name: "Hasheous",
    color: "var(--r-color-provider-hasheous)",
    logo: "/assets/scrappers/hasheous.png",
    url: null,
  },
  {
    key: "flashpoint_id",
    name: "Flashpoint Archive",
    color: "var(--r-color-provider-flashpoint)",
    logo: "/assets/scrappers/flashpoint.png",
    url: null,
  },
  {
    key: "hltb_id",
    name: "HowLongToBeat",
    color: "var(--r-color-provider-hltb)",
    logo: "/assets/scrappers/hltb.png",
    url: (id) => `https://howlongtobeat.com/game/${id}`,
  },
];

/**
 * Resolves a provider's external ID on a ROM, returning null when
 * unset. Centralised so callers don't have to deal with the
 * `null | undefined | "" | 0` matrix.
 */
export function providerId(
  rom: DetailedRom,
  provider: Provider,
): string | number | null {
  const v = rom[provider.key];
  if (v === null || v === undefined || v === "" || v === 0) return null;
  return v as string | number;
}
