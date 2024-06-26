import cronstrue from "cronstrue";
import type { SimpleRom } from "@/stores/roms";

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

export const defaultAvatarPath = "/assets/default/user.png";

export function normalizeString(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

export function convertCronExperssion(expression: string) {
  let convertedExpression = cronstrue.toString(expression, { verbose: true });
  convertedExpression =
    convertedExpression.charAt(0).toLocaleLowerCase() +
    convertedExpression.substr(1);
  return convertedExpression;
}

export function getDownloadLink({
  rom,
  files = [],
}: {
  rom: SimpleRom;
  files?: string[];
}) {
  const queryParams = new URLSearchParams();
  if (files.length) {
    files.forEach((file) => queryParams.append("files", file));
  }
  return `/api/roms/${rom.id}/content/${
    rom.file_name
  }?${queryParams.toString()}`;
}

/**
 * Format bytes as human-readable text.
 *
 * @param bytes Number of bytes.
 * @param decimals Number of decimal places to display.
 *
 * @return Formatted string.
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
 *
 * Format timestamp to human-readable text
 *
 * @param string timestamp
 * @returns string Formatted timestamp
 */
export function formatTimestamp(timestamp: string | null) {
  if (!timestamp) return "-";

  const date = new Date(timestamp);
  return date.toLocaleString("en-GB");
}

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

const _EJS_CORES_MAP = {
  "3do": ["opera"],
  amiga: ["puae"],
  arcade: [
    "mame2003",
    "mame2003_plus",
    "fbneo",
    "fbalpha2012_cps1",
    "fbalpha2012_cps2",
  ],
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
  n64: ["mupen64plus_next", "parallel-n64"],
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
  ps: ["pcsx_rearmed", "mednafen_psx"],
  segacd: ["genesis_plus_gx", "picodrive"],
  // sega32: ["picodrive"], // Broken: https://github.com/EmulatorJS/EmulatorJS/issues/579
  gamegear: ["genesis_plus_gx"],
  sms: ["genesis_plus_gx"],
  "sega-mark-iii": ["genesis_plus_gx"],
  "sega-game-box-9": ["genesis_plus_gx"],
  "sega-master-system-ii": ["genesis_plus_gx", "smsplus"],
  "master-system-super-compact": ["genesis_plus_gx"],
  "master-system-girl": ["genesis_plus_gx"],
  "genesis-slash-megadrive": ["genesis_plus_gx"],
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

export function getSupportedCores(platformSlug: string) {
  return _EJS_CORES_MAP[platformSlug.toLowerCase() as EJSPlatformSlug] || [];
}

export function isEmulationSupported(platformSlug: string) {
  return platformSlug.toLowerCase() in _EJS_CORES_MAP;
}
