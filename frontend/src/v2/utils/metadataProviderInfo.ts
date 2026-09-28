// Display registry for the metadata-provider *source* surfaces: the
// settings tiles, the setup wizard's metadata step and the scan
// reference dialog all render their cards from this single list, so
// names, logos, links and locale keys never drift between them.
// (Per-ROM match chips have their own registry in metadataProviders.ts,
// keyed by the ROM id fields instead of the provider slug.)
import type { MetadataSourcesDict } from "@/__generated__";
import type { MetadataProviderKey } from "./metadataProviderGroups";

export interface MetadataProviderInfo {
  /** Slug the backend `MetadataSource` enum and the heartbeat store use. */
  key: MetadataProviderKey;
  name: string;
  /** Logo path under /assets/scrappers/. */
  logo: string;
  website: string;
  /** Where to sign up / read how to get access. */
  docsUrl: string;
  /** True when the provider is enabled by configuring an API key /
   *  credentials (so a "get API key" link is meaningful). False for
   *  free/public providers toggled by a plain `*_API_ENABLED` flag. */
  requiresKey: boolean;
  /** Heartbeat flag that says whether the provider is enabled server-side. */
  enabledFlag: keyof MetadataSourcesDict;
  /** Locale key for the one-line description (setup wizard, scan dialog). */
  descKey: string;
  /** Locale key for the env-var / config instructions. */
  setupKey: string;
  /** Optional locale key for a warning / caveat pill. */
  caveatKey?: string;
  /** Optional locale key for the settings tile descriptor: what a source
   *  contributes, or the platforms it covers. */
  subtitleKey?: string;
}

export const METADATA_PROVIDER_INFO: readonly MetadataProviderInfo[] = [
  {
    key: "igdb",
    name: "IGDB",
    logo: "/assets/scrappers/igdb.png",
    website: "https://www.igdb.com",
    docsUrl: "https://api-docs.igdb.com/#account-creation",
    requiresKey: true,
    enabledFlag: "IGDB_API_ENABLED",
    descKey: "setup.provider-igdb-desc",
    setupKey: "setup.provider-igdb-setup",
  },
  {
    key: "ss",
    name: "ScreenScraper",
    logo: "/assets/scrappers/ss.png",
    website: "https://www.screenscraper.fr",
    docsUrl: "https://www.screenscraper.fr/membreinscription.php",
    requiresKey: true,
    enabledFlag: "SS_API_ENABLED",
    descKey: "setup.provider-ss-desc",
    setupKey: "setup.provider-ss-setup",
  },
  {
    key: "moby",
    name: "MobyGames",
    logo: "/assets/scrappers/moby.png",
    website: "https://www.mobygames.com",
    docsUrl: "https://www.mobygames.com/info/api/",
    requiresKey: true,
    enabledFlag: "MOBY_API_ENABLED",
    descKey: "setup.provider-moby-desc",
    setupKey: "setup.provider-moby-setup",
    caveatKey: "setup.provider-moby-caveat",
  },
  {
    key: "launchbox",
    name: "LaunchBox",
    logo: "/assets/scrappers/launchbox.png",
    website: "https://www.launchbox-app.com",
    docsUrl: "https://gamesdb.launchbox-app.com",
    requiresKey: false,
    enabledFlag: "LAUNCHBOX_API_ENABLED",
    descKey: "setup.provider-launchbox-desc",
    setupKey: "setup.provider-launchbox-setup",
    caveatKey: "setup.provider-launchbox-caveat",
  },
  {
    key: "flashpoint",
    name: "Flashpoint",
    logo: "/assets/scrappers/flashpoint.png",
    website: "https://flashpointarchive.org",
    docsUrl: "https://flashpointarchive.org/datahub/Flashpoint_API",
    requiresKey: false,
    enabledFlag: "FLASHPOINT_API_ENABLED",
    descKey: "setup.provider-flashpoint-desc",
    setupKey: "setup.provider-flashpoint-setup",
  },
  {
    key: "steam",
    name: "Steam",
    logo: "/assets/scrappers/steam.png",
    website: "https://store.steampowered.com",
    docsUrl: "https://store.steampowered.com",
    requiresKey: false,
    enabledFlag: "STEAM_API_ENABLED",
    descKey: "setup.provider-steam-desc",
    setupKey: "setup.provider-steam-setup",
    caveatKey: "setup.provider-steam-caveat",
    subtitleKey: "settings.metadata-subtitle-pc",
  },
  {
    key: "ra",
    name: "RetroAchievements",
    logo: "/assets/scrappers/ra.png",
    website: "https://retroachievements.org",
    docsUrl: "https://retroachievements.org/APIDemo.php",
    requiresKey: true,
    enabledFlag: "RA_API_ENABLED",
    descKey: "setup.provider-ra-desc",
    setupKey: "setup.provider-ra-setup",
    caveatKey: "setup.provider-ra-caveat",
    subtitleKey: "settings.metadata-subtitle-achievements",
  },
  {
    key: "sgdb",
    name: "SteamGridDB",
    logo: "/assets/scrappers/sgdb.png",
    website: "https://www.steamgriddb.com",
    docsUrl: "https://www.steamgriddb.com/profile/preferences/api",
    requiresKey: true,
    enabledFlag: "STEAMGRIDDB_API_ENABLED",
    descKey: "setup.provider-sgdb-desc",
    setupKey: "setup.provider-sgdb-setup",
    caveatKey: "setup.provider-sgdb-caveat",
    subtitleKey: "settings.metadata-subtitle-cover-art",
  },
  {
    key: "hltb",
    name: "HowLongToBeat",
    logo: "/assets/scrappers/hltb.png",
    website: "https://howlongtobeat.com",
    docsUrl: "https://howlongtobeat.com",
    requiresKey: false,
    enabledFlag: "HLTB_API_ENABLED",
    descKey: "setup.provider-hltb-desc",
    setupKey: "setup.provider-hltb-setup",
    caveatKey: "setup.provider-hltb-caveat",
    subtitleKey: "settings.metadata-subtitle-completion",
  },
  {
    key: "demozoo",
    name: "Demozoo",
    logo: "/assets/scrappers/demozoo.png",
    website: "https://demozoo.org",
    docsUrl: "https://demozoo.org/api/docs/",
    requiresKey: false,
    enabledFlag: "DEMOZOO_API_ENABLED",
    descKey: "setup.provider-demozoo-desc",
    setupKey: "setup.provider-demozoo-setup",
    caveatKey: "setup.provider-demozoo-caveat",
    subtitleKey: "settings.metadata-subtitle-demoscene",
  },
  {
    key: "pouet",
    name: "Pouët",
    logo: "/assets/scrappers/pouet.png",
    website: "https://www.pouet.net",
    docsUrl: "https://api.pouet.net/",
    requiresKey: false,
    enabledFlag: "POUET_API_ENABLED",
    descKey: "setup.provider-pouet-desc",
    setupKey: "setup.provider-pouet-setup",
    caveatKey: "setup.provider-pouet-caveat",
    subtitleKey: "settings.metadata-subtitle-demoscene",
  },
  {
    key: "csdb",
    name: "CSDb",
    logo: "/assets/scrappers/csdb.png",
    website: "https://csdb.dk",
    docsUrl: "https://csdb.dk/webservice/",
    requiresKey: false,
    enabledFlag: "CSDB_API_ENABLED",
    descKey: "setup.provider-csdb-desc",
    setupKey: "setup.provider-csdb-setup",
    caveatKey: "setup.provider-csdb-caveat",
    subtitleKey: "settings.metadata-subtitle-demoscene",
  },
  {
    key: "hasheous",
    name: "Hasheous",
    logo: "/assets/scrappers/hasheous.png",
    website: "https://hasheous.org",
    docsUrl: "https://hasheous.org/index.html?page=apidocs",
    requiresKey: false,
    enabledFlag: "HASHEOUS_API_ENABLED",
    descKey: "setup.proxy-hasheous-desc",
    setupKey: "setup.proxy-hasheous-setup",
    caveatKey: "setup.proxy-hasheous-caveat",
  },
  {
    key: "playmatch",
    name: "PlayMatch",
    logo: "/assets/scrappers/playmatch.png",
    website: "https://github.com/RetroRealm/playmatch",
    docsUrl: "https://github.com/RetroRealm/playmatch",
    requiresKey: false,
    enabledFlag: "PLAYMATCH_API_ENABLED",
    descKey: "setup.proxy-playmatch-desc",
    setupKey: "setup.proxy-playmatch-setup",
    caveatKey: "setup.proxy-playmatch-caveat",
  },
];
