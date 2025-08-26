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
    image: "/assets/console/default/systems/3do.svg",
    background: "linear-gradient(135deg,#4e4376,#2b5876)",
    accent: "#6f63b4",
  },
  amiga: {
    label: "Amiga",
    shortName: "Amiga",
    image: "/assets/console/default/systems/amiga.svg",
    background: "linear-gradient(135deg,#0093e9,#80d0c7)",
    accent: "#33b1ff",
  },
  arcade: {
    label: "Arcade / MAME",
    shortName: "Arcade",
    image: "/assets/console/default/systems/arcade.svg",
    background: "linear-gradient(135deg,#d73266,#8b1538)",
    accent: "#d73266",
  },
  mame: {
    label: "Arcade / MAME",
    shortName: "Arcade",
    image: "/assets/console/default/systems/arcade.svg",
    background: "linear-gradient(135deg,#d73266,#8b1538)",
    accent: "#d73266",
  },
  atari2600: {
    label: "Atari 2600",
    shortName: "2600",
    image: "/assets/console/default/systems/atari2600.svg",
    background: "linear-gradient(135deg,#c04848,#480048)",
    accent: "#ff6a6a",
  },
  atari5200: {
    label: "Atari 5200",
    shortName: "5200",
    image: "/assets/console/default/systems/atari5200.svg",
    background: "linear-gradient(135deg,#3a6073,#16222a)",
    accent: "#4fa3c7",
  },
  atari7800: {
    label: "Atari 7800",
    shortName: "7800",
    image: "/assets/console/default/systems/atari7800.svg",
    background: "linear-gradient(135deg,#870000,#190a05)",
    accent: "#ff3030",
  },
  jaguar: {
    label: "Atari Jaguar",
    shortName: "Jaguar",
    image: "/assets/console/default/systems/jaguar.svg",
    background: "linear-gradient(135deg,#000000,#434343)",
    accent: "#ff0015",
  },
  lynx: {
    label: "Atari Lynx",
    shortName: "Lynx",
    image: "/assets/console/default/systems/lynx.svg",
    background: "linear-gradient(135deg,#485563,#29323c)",
    accent: "#ffa733",
  },
  c64: {
    label: "Commodore 64",
    shortName: "C64",
    image: "/assets/console/default/systems/c64.svg",
    background: "linear-gradient(135deg,#614385,#516395)",
    accent: "#8b7ad6",
  },
  colecovision: {
    label: "ColecoVision",
    shortName: "Coleco",
    image: "/assets/console/default/systems/coleco.svg",
    background: "linear-gradient(135deg,#134e5e,#71b280)",
    accent: "#34c686",
  },
  doom: {
    label: "DOOM",
    shortName: "DOOM",
    image: "/assets/console/default/systems/doom.svg",
    background: "linear-gradient(135deg,#636363,#0f0f0f)",
    accent: "#ff9800",
  },
  "neo-geo-pocket": {
    label: "Neo Geo Pocket",
    shortName: "NGP",
    image: "/assets/console/default/systems/ngp.svg",
    background: "linear-gradient(135deg,#1e3c72,#2a5298)",
    accent: "#2e6dff",
  },
  "neo-geo-pocket-color": {
    label: "Neo Geo Pocket Color",
    shortName: "NGPC",
    image: "/assets/console/default/systems/ngpc.svg",
    background: "linear-gradient(135deg,#42275a,#734b6d)",
    accent: "#b667d0",
  },
  dos: {
    label: "MS-DOS",
    shortName: "DOS",
    image: "/assets/console/default/systems/dos.svg",
    background: "linear-gradient(135deg,#203a43,#2c5364)",
    accent: "#3fa7d6",
  },
  n64: {
    label: "Nintendo 64",
    shortName: "N64",
    image: "/assets/console/default/systems/n64.svg",
    background: "linear-gradient(135deg,#ffd700,#ff8c00)",
    accent: "#ffd700",
  },
  nes: {
    label: "Nintendo Entertainment System (NES)",
    shortName: "NES",
    image: "/assets/console/default/systems/nes.svg",
    background: "linear-gradient(135deg,#cc2936,#8b1538)",
    accent: "#cc2936",
  },
  famicom: {
    label: "Nintendo Family Computer (Famicom)",
    shortName: "Famicom",
    image: "/assets/console/default/systems/nes.svg",
    background: "linear-gradient(135deg,#cc2936,#8b1538)",
    accent: "#cc2936",
  },
  nds: {
    label: "Nintendo DS",
    shortName: "NDS",
    image: "/assets/console/default/systems/nds.svg",
    background: "linear-gradient(135deg,#56ccf2,#2f80ed)",
    accent: "#2f80ed",
  },
  gb: {
    label: "Game Boy",
    shortName: "GB",
    image: "/assets/console/default/systems/gbc.svg",
    background: "linear-gradient(135deg,#8fbc8f,#556b2f)",
    accent: "#8fbc8f",
  },
  gbc: {
    label: "Game Boy Color",
    shortName: "GBC",
    image: "/assets/console/default/systems/gbc.svg",
    background: "linear-gradient(135deg,#20b2aa,#008b8b)",
    accent: "#20b2aa",
  },
  gba: {
    label: "Game Boy Advance",
    shortName: "GBA",
    image: "/assets/console/default/systems/gba.svg",
    background: "linear-gradient(135deg,#9370db,#4b0082)",
    accent: "#9370db",
  },
  "pc-fx": {
    label: "PC-FX",
    shortName: "PC-FX",
    image: "/assets/console/default/systems/pcfx.svg",
    background: "linear-gradient(135deg,#41295a,#2f0743)",
    accent: "#b44cff",
  },
  psx: {
    label: "PlayStation (PS)",
    shortName: "PS1",
    image: "/assets/console/default/systems/psx.svg",
    background: "linear-gradient(135deg,#4169e1,#191970)",
    accent: "#4169e1",
  },
  sega32: {
    label: "Sega 32X",
    shortName: "32X",
    image: "/assets/console/default/systems/32x.svg",
    background: "linear-gradient(135deg,#f7971e,#ffd200)",
    accent: "#ffbf00",
  },
  segacd: {
    label: "Sega CD",
    shortName: "Sega CD",
    image: "/assets/console/default/systems/segacd.svg",
    background: "linear-gradient(135deg,#2980b9,#2c3e50)",
    accent: "#4fa3ff",
  },
  gamegear: {
    label: "Sega Game Gear",
    shortName: "GG",
    image: "/assets/console/default/systems/gamegear.svg",
    background: "linear-gradient(135deg,#141e30,#243b55)",
    accent: "#4f7fbf",
  },
  sms: {
    label: "Sega Master System",
    shortName: "SMS",
    image: "/assets/console/default/systems/sms.svg",
    background: "linear-gradient(135deg,#ff6347,#dc143c)",
    accent: "#ff6347",
  },
  genesis: {
    label: "Sega Genesis / Megadrive",
    shortName: "Genesis",
    image: "/assets/console/default/systems/genesis.svg",
    background: "linear-gradient(135deg,#1e90ff,#0f4c75)",
    accent: "#1e90ff",
  },
  saturn: {
    label: "Sega Saturn",
    shortName: "Saturn",
    image: "/assets/console/default/systems/saturn.svg",
    background: "linear-gradient(135deg,#141e30,#243b55)",
    accent: "#4f7fbf",
  },
  snes: {
    label: "Super Nintendo Entertainment System (SNES)",
    shortName: "SNES",
    image: "/assets/console/default/systems/snes.svg",
    background: "linear-gradient(135deg,#e22828,#f81414)",
    accent: "#e22828",
  },
  sfam: {
    label: "Super Famicom",
    shortName: "SFC",
    image: "/assets/console/default/systems/snes.svg",
    background: "linear-gradient(135deg,#e22828,#f81414)",
    accent: "#e22828",
  },
  tg16: {
    label: "TurboGrafx-16 / PC Engine",
    shortName: "TG-16",
    image: "/assets/console/default/systems/pcengine.svg",
    background: "linear-gradient(135deg,#ff9966,#ff5e62)",
    accent: "#ff7b54",
  },
  virtualboy: {
    label: "Virtual Boy",
    shortName: "VBoy",
    image: "/assets/console/default/systems/virtualboy.svg",
    background: "linear-gradient(135deg,#8e0e00,#1f1c18)",
    accent: "#ff2a2a",
  },
  wonderswan: {
    label: "WonderSwan",
    shortName: "WS",
    image: "/assets/console/default/systems/wonderswan.svg",
    background: "linear-gradient(135deg,#457fca,#5691c8)",
    accent: "#4f8edb",
  },
  "wonderswan-color": {
    label: "WonderSwan Color",
    shortName: "WSC",
    image: "/assets/console/default/systems/wonderswancolor.svg",
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
