import cronstrue from "cronstrue";

export const views: Record<
  number,
  {
    view: string;
    icon: string;
    "size-xl": number;
    "size-lg": number;
    "size-md": number;
    "size-sm": number;
    "size-xs": number;
    "size-cols": number;
  }
> = {
  0: {
    view: "small",
    icon: "mdi-view-comfy",
    "size-xl": 1,
    "size-lg": 1,
    "size-md": 2,
    "size-sm": 2,
    "size-xs": 3,
    "size-cols": 4,
  },
  1: {
    view: "big",
    icon: "mdi-view-module",
    "size-xl": 2,
    "size-lg": 2,
    "size-md": 3,
    "size-sm": 3,
    "size-xs": 6,
    "size-cols": 6,
  },
  2: {
    view: "list",
    icon: "mdi-view-list",
    "size-xl": 12,
    "size-lg": 12,
    "size-md": 12,
    "size-sm": 12,
    "size-xs": 12,
    "size-cols": 12,
  },
};

export const defaultAvatarPath = "/assets/default/user.png";

export function toTop() {
  window.scrollTo({
    top: 0,
    left: 0,
    behavior: "smooth",
  });
}

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

export const platformSlugEJSPlatformMap: Record<string, string> = {
  "3do": "3do",
  amiga: "amiga",
  arcade: "arcade",
  atari2600: "atari2600",
  atari5200: "atari5200",
  atari7800: "atari7800",
  c64: "c64",
  colecovision: "coleco",
  jaguar: "jaguar",
  lynx: "lynx",
  mame: "mame2003",
  "neo-geo-pocket": "ngp",
  "neo-geo-pocket-color": "ngp",
  nes: "nes",
  famicom: "nes",
  n64: "n64",
  nds: "nds",
  gba: "gba",
  gb: "gb",
  gbc: "gb",
  "pc-fx": "pcfx",
  ps: "psx",
  psp: "psp",
  segacd: "segaCD",
  sega32: "sega32x",
  gamegear: "segaGG",
  sms: "segaMS",
  "genesis-slash-megadrive": "segaMD",
  saturn: "segaSaturn",
  snes: "snes",
  sfam: "snes",
  "turbografx16--1": "pce",
  virtualboy: "vb",
  wonderswan: "ws",
  "wonderswan-color": "ws",
} as const;

export const platformSlugEJSCoreMap: Record<string, string> = {
  "3do": "opera",
  amiga: "puae",
  arcade: "fbneo",
  atari2600: "stella2014",
  atari5200: "a5200",
  atari7800: "prosystem",
  c64: "vice_x64",
  colecovision: "gearcoleco",
  jaguar: "virtualjaguar",
  lynx: "handy",
  mame: "mame2003_plus",
  "neo-geo-pocket": "mednafen_ngp",
  "neo-geo-pocket-color": "mednafen_ngp",
  nes: "fceumm",
  "famicom": "fceumm",
  n64: "mupen64plus_next",
  nds: "melonds",
  gba: "mgba",
  gb: "gambatte",
  "pc-fx": "mednafen_pcfx",
  ps: "pcsx_rearmed",
  psp: "ppsspp",
  segacd: "genesis_plus_gx",
  sega32: "picodrive",
  gamegear: "genesis_plus_gx",
  sms: "genesis_plus_gx",
  "genesis-slash-megadrive": "genesis_plus_gx",
  saturn: "yabause",
  snes: "snes9x",
  sfam: "snes9x",
  "turbografx16--1": "mednafen_pce",
  virtualboy: "beetle_vb",
  wonderswan: "mednafen_wswan",
  "wonderswan-color": "mednafen_wswan",
} as const;
