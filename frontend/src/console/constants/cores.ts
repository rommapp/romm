/**
 * Mapping of platform slugs to EmulatorJS core names
 * This maps RomM platform slugs to the corresponding emulator cores
 * that EmulatorJS uses to run games for each platform.
 */
export const EMULATOR_CORE_MAP: Record<string, string> = {
  // Arcade
  arcade: 'mame2003_plus',
  mame: 'mame2003_plus',
  
  // Nintendo
  nes: 'nes',
  famicom: 'nes',
  snes: 'snes',
  supernintendo: 'snes',
  superfamicom: 'snes',
  n64: 'n64',
  gb: 'gb',
  gbc: 'gbc',
  gba: 'gba',
  
  // Sega
  genesis: 'segaMD',
  megadrive: 'segaMD',
  master_system: 'sms',
  mastersystem: 'sms',
  sms: 'sms',
  gg: 'gg',
  gamegear: 'gg',
  saturn: 'sat',
  
  // Sony
  psx: 'psx',
  ps1: 'psx',
  playstation: 'psx',
  ps2: 'ps2',
  ps3: 'ps3',
  psp: 'psp',
  
  // Atari
  atari2600: 'a26',
  atari7800: 'a78',
  lynx: 'lynx',
  atarilynx: 'lynx',
  
  // Other handhelds
  vb: 'vb',
  virtualboy: 'vb',
  wonderswan: 'ws',
  wonderswancolor: 'wsc',
  ngp: 'ngp',
  neogeopocket: 'ngp',
  ngpc: 'ngpc',
  neogeopocketcolor: 'ngpc',
  
  // PC Engine / TurboGrafx
  pce: 'pce',
  pcengine: 'pce',
  tg16: 'pce',
  sgx: 'sgx',
  pcfx: 'pcfx',
  
  // Computer platforms
  msx: 'msx',
  msx2: 'msx2',
  
  // Nintendo GameCube
  gamecube: 'gc',
  gc: 'gc',
};

/**
 * Get the EmulatorJS core name for a given platform slug
 * @param platformSlug - The platform slug from RomM
 * @returns The corresponding EmulatorJS core name, or null if not supported
 */
export function getCoreForPlatform(platformSlug: string): string | null {
  return EMULATOR_CORE_MAP[platformSlug.toLowerCase()] || null;
}
