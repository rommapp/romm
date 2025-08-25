export type SupportedPlatform = {
  label: string;
  shortName: string;
  image: string;
  background: string;
  accent: string;
};

const _SUPPORTED_PLATFORMS: Record<string, SupportedPlatform> = {
  "3do": {
    label: "3DO",
    shortName: "3DO",
    image: "/systems/3do.webp",
    background: "linear-gradient(135deg,#4e4376,#2b5876)",
    accent: "#6f63b4",
  },
  amiga: {
    label: "Amiga",
    shortName: "Amiga",
    image: "/systems/amiga.webp",
    background: "linear-gradient(135deg,#0093e9,#80d0c7)",
    accent: "#33b1ff",
  },
  arcade: {
    label: "Arcade / MAME",
    shortName: "Arcade",
    image: "/systems/arcade.webp",
    background: "linear-gradient(135deg,#d73266,#8b1538)",
    accent: "#d73266",
  },
  mame: {
    label: "Arcade / MAME",
    shortName: "Arcade",
    image: "/systems/arcade.webp",
    background: "linear-gradient(135deg,#d73266,#8b1538)",
    accent: "#d73266",
  },
  atari2600: {
    label: "Atari 2600",
    shortName: "2600",
    image: "/systems/atari2600.webp",
    background: "linear-gradient(135deg,#c04848,#480048)",
    accent: "#ff6a6a",
  },
  atari5200: {
    label: "Atari 5200",
    shortName: "5200",
    image: "/systems/atari5200.webp",
    background: "linear-gradient(135deg,#3a6073,#16222a)",
    accent: "#4fa3c7",
  },
  atari7800: {
    label: "Atari 7800",
    shortName: "7800",
    image: "/systems/atari7800.webp",
    background: "linear-gradient(135deg,#870000,#190a05)",
    accent: "#ff3030",
  },
  jaguar: {
    label: "Atari Jaguar",
    shortName: "Jaguar",
    image: "/systems/jaguar.webp",
    background: "linear-gradient(135deg,#000000,#434343)",
    accent: "#ff0015",
  },
  lynx: {
    label: "Atari Lynx",
    shortName: "Lynx",
    image: "/systems/lynx.webp",
    background: "linear-gradient(135deg,#485563,#29323c)",
    accent: "#ffa733",
  },
  c64: {
    label: "Commodore 64",
    shortName: "C64",
    image: "/systems/c64.webp",
    background: "linear-gradient(135deg,#614385,#516395)",
    accent: "#8b7ad6",
  },
  colecovision: {
    label: "ColecoVision",
    shortName: "Coleco",
    image: "/systems/coleco.webp",
    background: "linear-gradient(135deg,#134e5e,#71b280)",
    accent: "#34c686",
  },
  doom: {
    label: "DOOM",
    shortName: "DOOM",
    image: "/systems/doom.webp",
    background: "linear-gradient(135deg,#636363,#0f0f0f)",
    accent: "#ff9800",
  },
  "neo-geo-pocket": {
    label: "Neo Geo Pocket",
    shortName: "NGP",
    image: "/systems/ngp.webp",
    background: "linear-gradient(135deg,#1e3c72,#2a5298)",
    accent: "#2e6dff",
  },
  "neo-geo-pocket-color": {
    label: "Neo Geo Pocket Color",
    shortName: "NGPC",
    image: "/systems/ngpc.webp",
    background: "linear-gradient(135deg,#42275a,#734b6d)",
    accent: "#b667d0",
  },
  dos: {
    label: "MS-DOS",
    shortName: "DOS",
    image: "/systems/dos.webp",
    background: "linear-gradient(135deg,#203a43,#2c5364)",
    accent: "#3fa7d6",
  },
  n64: {
    label: "Nintendo 64",
    shortName: "N64",
    image: "/systems/n64.webp",
    background: "linear-gradient(135deg,#ffd700,#ff8c00)",
    accent: "#ffd700",
  },
  nes: {
    label: "Nintendo Entertainment System (NES)",
    shortName: "NES",
    image: "/systems/nes.webp",
    background: "linear-gradient(135deg,#cc2936,#8b1538)",
    accent: "#cc2936",
  },
  famicom: {
    label: "Nintendo Family Computer (Famicom)",
    shortName: "Famicom",
    image: "/systems/nes.webp",
    background: "linear-gradient(135deg,#cc2936,#8b1538)",
    accent: "#cc2936",
  },
  nds: {
    label: "Nintendo DS",
    shortName: "NDS",
    image: "/systems/nds.webp",
    background: "linear-gradient(135deg,#56ccf2,#2f80ed)",
    accent: "#2f80ed",
  },
  gb: {
    label: "Game Boy",
    shortName: "GB",
    image: "/systems/gbc.webp",
    background: "linear-gradient(135deg,#8fbc8f,#556b2f)",
    accent: "#8fbc8f",
  },
  gbc: {
    label: "Game Boy Color",
    shortName: "GBC",
    image: "/systems/gbc.webp",
    background: "linear-gradient(135deg,#20b2aa,#008b8b)",
    accent: "#20b2aa",
  },
  gba: {
    label: "Game Boy Advance",
    shortName: "GBA",
    image: "/systems/gba.webp",
    background: "linear-gradient(135deg,#9370db,#4b0082)",
    accent: "#9370db",
  },
  "pc-fx": {
    label: "PC-FX",
    shortName: "PC-FX",
    image: "/systems/pcfx.webp",
    background: "linear-gradient(135deg,#41295a,#2f0743)",
    accent: "#b44cff",
  },
  psx: {
    label: "PlayStation (PS)",
    shortName: "PS1",
    image: "/systems/psx.webp",
    background: "linear-gradient(135deg,#4169e1,#191970)",
    accent: "#4169e1",
  },
  sega32: {
    label: "Sega 32X",
    shortName: "32X",
    image: "/systems/32x.webp",
    background: "linear-gradient(135deg,#f7971e,#ffd200)",
    accent: "#ffbf00",
  },
  segacd: {
    label: "Sega CD",
    shortName: "Sega CD",
    image: "/systems/segacd.webp",
    background: "linear-gradient(135deg,#2980b9,#2c3e50)",
    accent: "#4fa3ff",
  },
  gamegear: {
    label: "Sega Game Gear",
    shortName: "GG",
    image: "/systems/gamegear.webp",
    background: "linear-gradient(135deg,#141e30,#243b55)",
    accent: "#4f7fbf",
  },
  sms: {
    label: "Sega Master System",
    shortName: "SMS",
    image: "/systems/sms.webp",
    background: "linear-gradient(135deg,#ff6347,#dc143c)",
    accent: "#ff6347",
  },
  genesis: {
    label: "Sega Genesis / Megadrive",
    shortName: "Genesis",
    image: "/systems/genesis.webp",
    background: "linear-gradient(135deg,#1e90ff,#0f4c75)",
    accent: "#1e90ff",
  },
  saturn: {
    label: "Sega Saturn",
    shortName: "Saturn",
    image: "/systems/saturn.webp",
    background: "linear-gradient(135deg,#141e30,#243b55)",
    accent: "#4f7fbf",
  },
  snes: {
    label: "Super Nintendo Entertainment System (SNES)",
    shortName: "SNES",
    image: "/systems/snes.webp",
    background: "linear-gradient(135deg,#e22828,#f81414)",
    accent: "#e22828",
  },
  sfam: {
    label: "Super Famicom",
    shortName: "SFC",
    image: "/systems/snes.webp",
    background: "linear-gradient(135deg,#e22828,#f81414)",
    accent: "#e22828",
  },
  tg16: {
    label: "TurboGrafx-16 / PC Engine",
    shortName: "TG-16",
    image: "/systems/pcengine.webp",
    background: "linear-gradient(135deg,#ff9966,#ff5e62)",
    accent: "#ff7b54",
  },
  virtualboy: {
    label: "Virtual Boy",
    shortName: "VBoy",
    image: "/systems/virtualboy.webp",
    background: "linear-gradient(135deg,#8e0e00,#1f1c18)",
    accent: "#ff2a2a",
  },
  wonderswan: {
    label: "WonderSwan",
    shortName: "WS",
    image: "/systems/wonderswan.webp",
    background: "linear-gradient(135deg,#457fca,#5691c8)",
    accent: "#4f8edb",
  },
  "wonderswan-color": {
    label: "WonderSwan Color",
    shortName: "WSC",
    image: "/systems/wonderswancolor.webp",
    background: "linear-gradient(135deg,#396afc,#2948ff)",
    accent: "#456dff",
  },
};

export function isSupportedPlatform(slug: string): boolean {
  return Object.keys(_SUPPORTED_PLATFORMS).includes(slug);
}

export function getPlatformTheme(slug: string): SupportedPlatform {
  return _SUPPORTED_PLATFORMS[slug];
}
