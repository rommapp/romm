import cronstrue from "cronstrue";
import type { SimpleRom } from "@/stores/roms";
import type { Heartbeat } from "@/stores/heartbeat";
import type { RomFileSchema, RomUserStatus } from "@/__generated__";

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
    fileIDs.forEach((fileId) =>
      queryParams.append("file_ids", fileId.toString()),
    );
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
  return `${window.location.origin}${encodeURI(getDownloadPath({ rom, fileIDs }))}`;
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
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
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
  return date.toLocaleString("en-GB");
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
    case "ar":
    case "arabic":
      return "🇦🇪";
    case "da":
    case "danish":
      return "🇩🇰";
    case "de":
    case "german":
      return "🇩🇪";
    case "en":
    case "english":
      return "🇬🇧";
    case "es":
    case "spanish":
      return "🇪🇸";
    case "fi":
    case "finnish":
      return "🇫🇮";
    case "fr":
    case "french":
      return "🇫🇷";
    case "it":
    case "italian":
      return "🇮🇹";
    case "ja":
    case "japanese":
      return "🇯🇵";
    case "ko":
    case "korean":
      return "🇰🇷";
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
    case "ru":
    case "russian":
      return "🇷🇺";
    case "sv":
    case "swedish":
      return "🇸🇪";
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
const _EJS_CORES_MAP = {
  "3do": ["opera"],
  amiga: ["puae"],
  amigacd32: ["puae"],
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
  atari5200: ["a5200"],
  atari7800: ["prosystem"],
  cplus4: ["vice_xplus4"],
  c64: ["vice_x64sc", "vice_x64"],
  cpet: ["vice_xpet"],
  "commodore-64c": ["vice_x64sc", "vice_x64"],
  c128: ["vice_x128"],
  "commmodore-128": ["vice_x128"],
  colecovision: ["gearcoleco"],
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
  ps: ["pcsx_rearmed", "mednafen_psx_hw"],
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
  megadrive: ["genesis_plus_gx"],
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
  "turbografx16--1": ["mednafen_pce"],
  "vic-20": ["vice_xvic"],
  virtualboy: ["beetle_vb"],
  wonderswan: ["mednafen_wswan"],
  swancrystal: ["mednafen_wswan"],
  "wonderswan-color": ["mednafen_wswan"],
} as const;

export type EJSPlatformSlug = keyof typeof _EJS_CORES_MAP;

/**
 * Get the supported EJS cores for a given platform.
 *
 * @param platformSlug The platform slug.
 * @returns An array of supported cores.
 */
export function getSupportedEJSCores(platformSlug: string): string[] {
  const cores =
    _EJS_CORES_MAP[platformSlug.toLowerCase() as EJSPlatformSlug] || [];
  const threadsSupported = isEJSThreadsSupported();
  return cores.filter(
    (core) => !areThreadsRequiredForEJSCore(core) || threadsSupported,
  );
}

/**
 * Check if a given EJS core requires threads enabled.
 *
 * @param core The core name.
 * @returns True if threads are required, false otherwise.
 */
export function areThreadsRequiredForEJSCore(core: string): boolean {
  return ["ppsspp"].includes(core);
}

const canvas = document.createElement("canvas");
const gl =
  canvas.getContext("webgl") || canvas.getContext("experimental-webgl");

/**
 * Check if EJS emulation is supported for a given platform.
 *
 * @param platformSlug The platform slug.
 * @param heartbeat The heartbeat object.
 * @returns True if supported, false otherwise.
 */
export function isEJSEmulationSupported(
  platformSlug: string,
  heartbeat: Heartbeat,
) {
  return (
    !heartbeat.EMULATION.DISABLE_EMULATOR_JS &&
    getSupportedEJSCores(platformSlug).length > 0 &&
    gl instanceof WebGLRenderingContext
  );
}

/**
 * Check if EJS threads are supported.
 *
 * EmulatorJS threads are supported if SharedArrayBuffer is available.
 * Reference: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer
 *
 * @returns True if supported, false otherwise.
 */
export function isEJSThreadsSupported(): boolean {
  return typeof SharedArrayBuffer !== "undefined";
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
  megadrive: "segaMD",
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
 * @returns True if supported, false otherwise.
 */
export function isRuffleEmulationSupported(
  platformSlug: string,
  heartbeat: Heartbeat,
) {
  return (
    ["flash", "browser"].includes(platformSlug.toLowerCase()) &&
    !heartbeat.EMULATION.DISABLE_RUFFLE_RS
  );
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
export function getStatusKeyForText(text: string) {
  return inverseRomStatusMap[text];
}

export function is3DSCIAFile(rom: SimpleRom): boolean {
  return rom.fs_extension.toLowerCase() == "cia";
}

export function get3DSCIAFiles(rom: SimpleRom): RomFileSchema[] {
  return rom.files.filter((file) =>
    file.file_name.toLowerCase().endsWith(".cia"),
  );
}

/**
 * Check if a ROM is a valid 3DS game
 * @param rom The ROM object.
 * @returns True if the ROM is a valid 3DS game, false otherwise.
 */
export function is3DSCIARom(rom: SimpleRom): boolean {
  if (rom.platform_slug !== "3ds") return false;

  const hasValidExtension = is3DSCIAFile(rom);
  const hasValidFile = get3DSCIAFiles(rom).length > 0;

  return hasValidExtension || hasValidFile;
}
