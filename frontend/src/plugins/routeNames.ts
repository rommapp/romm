export const ROUTES = {
  SETUP: "setup",
  LOGIN: "login",
  RESET_PASSWORD: "reset-password",
  REGISTER: "register",
  MAIN: "main",
  HOME: "home",
  SEARCH: "search",
  MUSIC: "music",
  PLATFORM: "platform",
  COLLECTION: "collection",
  VIRTUAL_COLLECTION: "virtual-collection",
  SMART_COLLECTION: "smart-collection",
  ROM: "rom",
  EMULATORJS: "emulatorjs",
  JSDOS: "jsdos",
  PICO8: "pico8",
  RUFFLE: "ruffle",
  STREAM: "stream",
  STREAM_DESKTOP: "stream-desktop",
  SCAN: "scan",
  UPLOAD: "upload",
  ACTIVITY: "activity",
  USER_PROFILE: "user-profile",
  USER_INTERFACE: "user-interface",
  LIBRARY_MANAGEMENT: "library-management",
  SCAN_SETTINGS: "scan-settings",
  CONVERSION_SETTINGS: "conversion-settings",
  METADATA_SOURCES: "metadata-sources",
  CLIENT_API_TOKENS: "client-api-tokens",
  ADMINISTRATION: "administration",
  SERVER_STATS: "server-stats",
  LOGS: "logs",
  PAIR: "pair",
  PAIR_DEVICE: "pair-device",
  APRIL_FOOLS: "april-fools",
  CONSOLE_HOME: "console-home",
  CONSOLE_PLATFORM: "console-platform",
  CONSOLE_COLLECTION: "console-collection",
  CONSOLE_SMART_COLLECTION: "console-smart-collection",
  CONSOLE_VIRTUAL_COLLECTION: "console-virtual-collection",
  CONSOLE_ROM: "console-rom",
  CONSOLE_PLAY: "console-play",
  PLATFORMS_INDEX: "platforms-index",
  COLLECTIONS_INDEX: "collections-index",
  CONTROLLER_DEBUG: "controller-debug",
  NOT_FOUND: "404",
} as const;

export type RouteName = (typeof ROUTES)[keyof typeof ROUTES];

const authExemptRoutes = [
  ROUTES.LOGIN,
  ROUTES.SETUP,
  ROUTES.RESET_PASSWORD,
  ROUTES.REGISTER,
  ROUTES.PAIR,
] as const;

type AuthExemptRoute = (typeof authExemptRoutes)[number];

export function isAuthExemptRoute(route: string): route is AuthExemptRoute {
  return (authExemptRoutes as readonly string[]).includes(route);
}
