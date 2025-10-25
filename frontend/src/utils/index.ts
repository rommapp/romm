import cronstrue from "cronstrue";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useDisplay } from "vuetify";
import type { RomFileSchema, RomUserStatus } from "@/__generated__";
import type { Config } from "@/stores/config";
import type { Heartbeat } from "@/stores/heartbeat";
import storeNavigation from "@/stores/navigation";
import type { SimpleRom } from "@/stores/roms";

/**
 * Views configuration object.
 */
export const views: Record<
  number,
  {
    view: string;
    icon: string;
    "size-xl": number;
    "size-lg": number;
    "size-md": number;
    "size-sm": number;
    "size-cols": number;
  }
> = {
  0: {
    view: "small",
    icon: "mdi-view-comfy",
    "size-cols": 4,
    "size-sm": 2,
    "size-md": 2,
    "size-lg": 1,
    "size-xl": 1,
  },
  1: {
    view: "big",
    icon: "mdi-view-module",
    "size-cols": 6,
    "size-sm": 3,
    "size-md": 3,
    "size-lg": 2,
    "size-xl": 2,
  },
  2: {
    view: "list",
    icon: "mdi-view-list",
    "size-cols": 12,
    "size-sm": 12,
    "size-md": 12,
    "size-lg": 12,
    "size-xl": 12,
  },
};

/**
 * Get icon associated to role.
 *
 * @param role The role as string.
 * @returns The mdi icon string.
 */
export function getRoleIcon(role: string) {
  switch (role) {
    case "admin":
      return "mdi-shield-crown-outline";
    case "editor":
      return "mdi-file-edit-outline";
    case "viewer":
      return "mdi-book-open-variant-outline";
    default:
      return "mdi-account";
  }
}

/**
 * Default path for user avatars.
 */
export const defaultAvatarPath = "/assets/default/user.svg";

/**
 * Normalize a string by converting it to lowercase and removing diacritics.
 *
 * @param s The string to normalize.
 * @returns The normalized string.
 */
export function normalizeString(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

/**
 * Convert a cron expression to a human-readable string.
 *
 * @param expression The cron expression to convert.
 * @returns The human-readable string.
 */
export function convertCronExperssion(expression: string) {
  let convertedExpression = cronstrue.toString(expression, { verbose: true });
  convertedExpression =
    convertedExpression.charAt(0).toLocaleLowerCase() +
    convertedExpression.substr(1);
  return convertedExpression;
}

/**
 * Generate a download link for ROM content.
 *
 * @param rom The ROM object.
 * @param files Optional array of file names to include in the download.
 * @returns The download link.
 */
export function getDownloadPath({
  rom,
  fileIDs = [],
}: {
  rom: SimpleRom;
  fileIDs?: number[];
}) {
  const queryParams = new URLSearchParams();
  if (fileIDs.length > 0) {
    queryParams.append("file_ids", fileIDs.join(","));
  }
  return `/api/roms/${rom.id}/content/${rom.fs_name}?${queryParams.toString()}`;
}

export function getDownloadLink({
  rom,
  fileIDs = [],
}: {
  rom: SimpleRom;
  fileIDs?: number[];
}) {
  return `${window.location.origin}${encodeURI(
    getDownloadPath({ rom, fileIDs }),
  )}`;
}

/**
 * Format bytes as human-readable text.
 *
 * @param bytes Number of bytes.
 * @param decimals Number of decimal places to display.
 * @returns Formatted string.
 */
export function formatBytes(bytes: number, decimals = 2) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const dm = Math.max(0, decimals);
  const sizes = ["B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

/**
 * Format a timestamp to a human-readable string.
 *
 * @param timestamp The timestamp to format.
 * @returns The formatted timestamp.
 */
export function formatTimestamp(timestamp: string | null) {
  if (!timestamp) return "-";

  const date = new Date(timestamp);
  return date.toLocaleString("en-US");
}

/**
 * Convert a region code to an emoji.
 *
 * @param region The region code.
 * @returns The corresponding emoji.
 */
export function regionToEmoji(region: string) {
  switch (region.toLowerCase()) {
    case "as":
    case "australia":
      return "🇦🇺";
    case "a":
    case "asia":
      return "🌏";
    case "b":
    case "bra":
    case "brazil":
      return "🇧🇷";
    case "c":
    case "canada":
      return "🇨🇦";
    case "ch":
    case "chn":
    case "china":
      return "🇨🇳";
    case "e":
    case "eu":
    case "eur":
    case "europe":
      return "🇪🇺";
    case "f":
    case "france":
      return "🇫🇷";
    case "fn":
    case "finland":
      return "🇫🇮";
    case "g":
    case "germany":
      return "🇩🇪";
    case "gr":
    case "greece":
      return "🇬🇷";
    case "h":
    case "holland":
      return "🇳🇱";
    case "hk":
    case "hong kong":
      return "🇭🇰";
    case "i":
    case "italy":
      return "🇮🇹";
    case "j":
    case "jp":
    case "japan":
      return "🇯🇵";
    case "k":
    case "korea":
      return "🇰🇷";
    case "nl":
    case "netherlands":
      return "🇳🇱";
    case "no":
    case "norway":
      return "🇳🇴";
    case "pd":
    case "public domain":
      return "🇵🇱";
    case "r":
    case "russia":
      return "🇷🇺";
    case "s":
    case "spain":
      return "🇪🇸";
    case "sw":
    case "sweden":
      return "🇸🇪";
    case "t":
    case "taiwan":
      return "🇹🇼";
    case "u":
    case "us":
    case "usa":
      return "🇺🇸";
    case "uk":
    case "england":
      return "🇬🇧";
    case "unk":
    case "unknown":
      return "🌎";
    case "unl":
    case "unlicensed":
      return "🌎";
    case "w":
    case "global":
    case "world":
      return "🌎";
    default:
      return region;
  }
}

/**
 * Convert a language code to an emoji.
 *
 * @param language The language code.
 * @returns The corresponding emoji.
 */
export function languageToEmoji(language: string) {
  switch (language.toLowerCase()) {
    case "af":
    case "afrikaans":
      return "🇿🇦";
    case "ar":
    case "arabic":
      return "🇦🇪";
    case "be":
    case "belarusian":
      return "🇧🇾";
    case "bg":
    case "bulgarian":
      return "🇧🇬";
    case "ca":
    case "catalan":
      return "🇦🇩";
    case "cs":
    case "czech":
      return "🇨🇿";
    case "da":
    case "danish":
      return "🇩🇰";
    case "de":
    case "german":
      return "🇩🇪";
    case "el":
    case "greek":
      return "🇬🇷";
    case "en":
    case "english":
      return "🇬🇧";
    case "es":
    case "spanish":
      return "🇪🇸";
    case "et":
    case "estonian":
      return "🇪🇪";
    case "fi":
    case "finnish":
      return "🇫🇮";
    case "fr":
    case "french":
      return "🇫🇷";
    case "he":
    case "hebrew":
      return "🇮🇱";
    case "hi":
    case "hindi":
      return "🇮🇳";
    case "hr":
    case "croatian":
      return "🇭🇷";
    case "hu":
    case "hungarian":
      return "🇭🇺";
    case "hy":
    case "armenian":
      return "🇦🇲";
    case "id":
    case "indonesian":
      return "🇮🇩";
    case "is":
    case "icelandic":
      return "🇮🇸";
    case "it":
    case "italian":
      return "🇮🇹";
    case "ja":
    case "japanese":
      return "🇯🇵";
    case "ko":
    case "korean":
      return "🇰🇷";
    case "la":
    case "latin":
      return "🇻🇦";
    case "lt":
    case "lithuanian":
      return "🇱🇹";
    case "lv":
    case "latvian":
      return "🇱🇻";
    case "mk":
    case "macedonian":
      return "🇲🇰";
    case "nl":
    case "dutch":
      return "🇳🇱";
    case "no":
    case "norwegian":
      return "🇳🇴";
    case "pl":
    case "polish":
      return "🇵🇱";
    case "pt":
    case "portuguese":
      return "🇵🇹";
    case "ro":
    case "romanian":
      return "🇷🇴";
    case "ru":
    case "russian":
      return "🇷🇺";
    case "sk":
    case "slovak":
      return "🇸🇰";
    case "sl":
    case "slovenian":
      return "🇸🇮";
    case "sq":
    case "albanian":
      return "🇦🇱";
    case "sr":
    case "serbian":
      return "🇷🇸";
    case "sv":
    case "swedish":
      return "🇸🇪";
    case "th":
    case "thai":
      return "🇹🇭";
    case "tr":
    case "turkish":
      return "🇹🇷";
    case "uk":
    case "ukrainian":
      return "🇺🇦";
    case "vi":
    case "vietnamese":
      return "🇻🇳";
    case "zh":
    case "chinese":
      return "🇨🇳";
    case "nolang":
    case "no language":
      return "🌎";
    default:
      return language;
  }
}

/**
 * Map of supported EJS cores for each platform.
 */
const _EJS_CORES_MAP: Record<string, string[]> = {
  "3do": ["opera"],
  acpc: ["cap32", "crocods"],
  amiga: ["puae"],
  "amiga-cd32": ["puae"],
  arcade: [
    "mame2003",
    "mame2003_plus",
    "fbneo",
    "fbalpha2012_cps1",
    "fbalpha2012_cps2",
  ],
  neogeoaes: ["fbneo"],
  neogeomvs: ["fbneo"],
  atari2600: ["stella2014"],
  "atari-2600-plus": ["stella2014"],
  atari5200: ["a5200"],
  atari7800: ["prosystem"],
  "c-plus-4": ["vice_xplus4"],
  c64: ["vice_x64sc", "vice_x64"],
  cpet: ["vice_xpet"],
  "commodore-64c": ["vice_x64sc", "vice_x64"],
  c128: ["vice_x128"],
  "commmodore-128": ["vice_x128"],
  colecovision: ["gearcoleco"],
  doom: ["prboom"],
  dos: ["dosbox_pure"],
  jaguar: ["virtualjaguar"],
  lynx: ["handy"],
  "atari-lynx-mkii": ["handy"],
  "neo-geo-pocket": ["mednafen_ngp"],
  "neo-geo-pocket-color": ["mednafen_ngp"],
  nes: ["fceumm", "nestopia"],
  famicom: ["fceumm", "nestopia"],
  fds: ["fceumm", "nestopia"],
  "game-televisison": ["fceumm"],
  "new-style-nes": ["fceumm"],
  n64: ["mupen64plus_next", "parallel_n64"],
  "ique-player": ["mupen64plus_next"],
  nds: ["melonds", "desmume2015"],
  "nintendo-ds-lite": ["melonds", "desmume2015"],
  "nintendo-dsi": ["melonds", "desmume2015"],
  "nintendo-dsi-xl": ["melonds", "desmume2015"],
  gb: ["gambatte", "mgba"],
  "game-boy-pocket": ["gambatte", "mgba"],
  "game-boy-light": ["gambatte", "mgba"],
  gba: ["mgba"],
  "game-boy-adavance-sp": ["mgba"],
  "game-boy-micro": ["mgba"],
  gbc: ["gambatte", "mgba"],
  "pc-fx": ["mednafen_pcfx"],
  psx: ["pcsx_rearmed", "mednafen_psx_hw"],
  "philips-cd-i": ["same_cdi"],
  psp: ["ppsspp"],
  segacd: ["genesis_plus_gx", "picodrive"],
  sega32: ["picodrive"],
  gamegear: ["genesis_plus_gx"],
  sms: ["genesis_plus_gx"],
  "sega-mark-iii": ["genesis_plus_gx"],
  "sega-game-box-9": ["genesis_plus_gx"],
  "sega-master-system-ii": ["genesis_plus_gx", "smsplus"],
  "master-system-super-compact": ["genesis_plus_gx"],
  "master-system-girl": ["genesis_plus_gx"],
  genesis: ["genesis_plus_gx"],
  "sega-mega-drive-2-slash-genesis": ["genesis_plus_gx"],
  "sega-mega-jet": ["genesis_plus_gx"],
  "mega-pc": ["genesis_plus_gx"],
  "tera-drive": ["genesis_plus_gx"],
  "sega-nomad": ["genesis_plus_gx"],
  saturn: ["yabause"],
  snes: ["snes9x"],
  sfam: ["snes9x"],
  "super-nintendo-original-european-version": ["snes9x"],
  "super-famicom-shvc-001": ["snes9x"],
  "super-famicom-jr-model-shvc-101": ["snes9x"],
  "new-style-super-nes-model-sns-101": ["snes9x"],
  tg16: ["mednafen_pce"],
  "vic-20": ["vice_xvic"],
  virtualboy: ["beetle_vb"],
  wonderswan: ["mednafen_wswan"],
  swancrystal: ["mednafen_wswan"],
  "wonderswan-color": ["mednafen_wswan"],
  zsx: ["fuse"],
} as const;

export type EJSPlatformSlug = keyof typeof _EJS_CORES_MAP;

/**
 * Get the supported EJS cores for a given platform.
 *
 * @param platformSlug The platform slug.
 * @returns An array of supported cores.
 */
export function getSupportedEJSCores(platformSlug: string): string[] {
  return _EJS_CORES_MAP[platformSlug.toLowerCase() as EJSPlatformSlug] || [];
}

/**
 * Check if a given EJS core requires threads enabled.
 *
 * @param core The core name.
 * @returns True if threads are required, false otherwise.
 */
export function areThreadsRequiredForEJSCore(core: string): boolean {
  return ["dosbox_pure", "ppsspp"].includes(core);
}

const canvas = document.createElement("canvas");
const gl =
  canvas.getContext("webgl") || canvas.getContext("experimental-webgl");

/**
 * Check if EJS emulation is supported for a given platform.
 *
 * @param platformSlug The platform slug.
 * @param heartbeat The heartbeat object.
 * @param config Optional configuration object.
 * @returns True if supported, false otherwise.
 */
export function isEJSEmulationSupported(
  platformSlug: string,
  heartbeat: Heartbeat,
  config?: Config,
) {
  if (heartbeat.EMULATION.DISABLE_EMULATOR_JS) return false;

  const slug = config?.PLATFORMS_VERSIONS[platformSlug] || platformSlug;
  return (
    getSupportedEJSCores(slug).length > 0 && gl instanceof WebGLRenderingContext
  );
}

// This is a workaround to set the control scheme for Sega systems using the same cores
const _EJS_CONTROL_SCHEMES = {
  segacd: "segaCD",
  sega32: "sega32x",
  gamegear: "segaGG",
  sms: "segaMS",
  "sega-mark-iii": "segaMS",
  "sega-master-system-ii": "segaMS",
  "master-system-super-compact": "segaMS",
  "master-system-girl": "segaMS",
  genesis: "segaMD",
  "sega-mega-drive-2-slash-genesis": "segaMD",
  "sega-mega-jet": "segaMD",
  "mega-pc": "segaMD",
  "tera-drive": "segaMD",
  "sega-nomad": "segaMD",
  saturn: "segaSaturn",
};

type EJSControlSlug = keyof typeof _EJS_CONTROL_SCHEMES;

/**
 * Get the control scheme for a given platform.
 *
 * @param platformSlug The platform slug.
 * @returns The control scheme.
 */
export function getControlSchemeForPlatform(
  platformSlug: string,
): string | null {
  return platformSlug in _EJS_CONTROL_SCHEMES
    ? _EJS_CONTROL_SCHEMES[platformSlug as EJSControlSlug]
    : null;
}

/**
 * Check if Ruffle emulation is supported for a given platform.
 *
 * @param platformSlug The platform slug.
 * @param heartbeat The heartbeat object.
 * @param config Optional configuration object.
 * @returns True if supported, false otherwise.
 */
export function isRuffleEmulationSupported(
  platformSlug: string,
  heartbeat: Heartbeat,
  config?: Config,
) {
  if (heartbeat.EMULATION.DISABLE_RUFFLE_RS) return false;

  const slug = config?.PLATFORMS_VERSIONS[platformSlug] || platformSlug;
  return ["flash", "browser"].includes(slug.toLowerCase());
}

type PlayingStatus = RomUserStatus | "backlogged" | "now_playing" | "hidden";

/**
 * Map of ROM statuses to their corresponding emoji and text.
 */
export const romStatusMap: Record<
  PlayingStatus,
  { emoji: string; text: string }
> = {
  backlogged: { emoji: "🔜", text: "Backlogged" },
  now_playing: { emoji: "🕹️", text: "Now Playing" },
  incomplete: { emoji: "🚧", text: "Incomplete" },
  finished: { emoji: "🏁", text: "Finished" },
  completed_100: { emoji: "💯", text: "Completed 100%" },
  retired: { emoji: "🏴", text: "Retired" },
  never_playing: { emoji: "🚫", text: "Never Playing" },
  hidden: { emoji: "👻", text: "Hidden" },
};

/**
 * Inverse map of ROM statuses from text to status key.
 */
const inverseRomStatusMap = Object.fromEntries(
  Object.entries(romStatusMap).map(([key, value]) => [value.text, key]),
) as Record<string, PlayingStatus>;

/**
 * Get the emoji for a given ROM status.
 *
 * @param status The ROM status.
 * @returns The corresponding emoji.
 */
export function getEmojiForStatus(status: PlayingStatus) {
  if (status) {
    return romStatusMap[status].emoji;
  } else {
    return null;
  }
}

/**
 * Get the text for a given ROM status.
 *
 * @param status The ROM status.
 * @returns The corresponding text.
 */
export function getTextForStatus(status: PlayingStatus) {
  if (status) {
    return romStatusMap[status].text;
  } else {
    return null;
  }
}

/**
 * Get the status key for a given text.
 *
 * @param text The text to convert.
 * @returns The corresponding status key.
 */
export function getStatusKeyForText(text: string | null) {
  if (!text) return null;
  return inverseRomStatusMap[text];
}

export function isNintendoDSFile(rom: SimpleRom): boolean {
  return ["cia", "nds", "3ds", "dsi"].includes(rom.fs_extension.toLowerCase());
}

export function getNintendoDSFiles(rom: SimpleRom): RomFileSchema[] {
  return rom.files.filter((file) => {
    const fileName = file.file_name.toLowerCase();
    return (
      fileName.endsWith(".cia") ||
      fileName.endsWith(".nds") ||
      fileName.endsWith(".3ds") ||
      fileName.endsWith(".dsi")
    );
  });
}

/**
 * Check if a ROM is a valid NDS/3DS/DSi game
 * @param rom The ROM object.
 * @returns {boolean} True if the ROM is a valid game, otherwise false.
 */
export function isNintendoDSRom(rom: SimpleRom): boolean {
  if (
    !["3ds", "nds", "new-nintendo-3ds", "nintendo-dsi"].includes(
      rom.platform_slug,
    )
  )
    return false;

  const hasValidExtension = isNintendoDSFile(rom);
  const hasValidFile = getNintendoDSFiles(rom).length > 0;

  return hasValidExtension || hasValidFile;
}

export function calculateMainLayoutWidth() {
  const { smAndDown } = useDisplay();
  const navigationStore = storeNavigation();
  const { mainBarCollapsed } = storeToRefs(navigationStore);
  const calculatedWidth = computed(() => {
    return smAndDown.value
      ? "calc(100% - 16px) !important"
      : mainBarCollapsed.value
        ? "calc(100% - 76px) !important"
        : "calc(100% - 106px) !important";
  });

  return { calculatedWidth };
}

/**
 * Get the icon for a given platform category.
 *
 * @param category The platform category.
 * @returns The corresponding icon.
 */
export function platformCategoryToIcon(category: string) {
  if (!category) return "";
  switch (category.toLowerCase()) {
    case "console":
      return "mdi-gamepad-variant";
    case "computer":
      return "mdi-desktop-classic";
    case "portable console":
      return "mdi-nintendo-game-boy";
    case "arcade":
      return "mdi-gamepad-circle";
    case "operating system":
      return "mdi-monitor-shimmer";
    case "platform":
      return "mdi-desktop-tower-monitor";
    case "unknown":
    default:
      return "";
  }
}

export const FRONTEND_RESOURCES_PATH = "/assets/romm/resources";

export const CD_BASED_SYSTEMS = new Set([
  "3do", // 3DO
  "amiga-cd32", // Amiga CD32
  "atari-jaguar-cd", // Atari Jaguar CD
  "philips-cd-i", // Philips CD-i
  "commodore-cdtv", // Commodore CDTV
  "dc", // Dreamcast
  "fm-towns", // FM Towns
  "hyperscan", // HyperScan
  "laseractive", // LaserActive
  "neo-geo-cd", // Neo Geo CD
  "ngc", // Nintendo GameCube
  "pc-fx", // PC-FX
  "psx", // PlayStation
  "ps2", // PlayStation 2
  "ps3", // PlayStation 3
  "ps4", // PlayStation 4
  "ps5", // PlayStation 5
  "psp", // PlayStation Portable
  "segacd", // Sega CD
  "series-x-s", // Xbox Series X/S
  "saturn", // Sega Saturn
  "super-nes-cd-rom-system", // Super NES CD-ROM System
  "tandy-vis", // Tandy Video Information System
  "tg16", // TurboGrafx-16
  "vflash", // V.Flash
  "wii", // Wii
  "wiiu", // Wii U
  "xbox", // Xbox
  "xbox360", // Xbox 360
  "xboxone", // Xbox One
]);

export function isCDBasedSystem(platformSlug: string): boolean {
  return CD_BASED_SYSTEMS.has(platformSlug.toLowerCase());
}
