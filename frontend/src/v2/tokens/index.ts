// RomM v2 Design Tokens
//
// The system is built on a near-black base
// with translucent white surfaces and 1-2 brand accents — a "glass over dark
// artwork" language rather than solid cards on a solid background. CSS
// custom properties are mirrored in src/v2/styles/tokens.css and must be
// kept in sync.

export const colorBrand = {
  // Match v1's purple-first palette (dark-mode values). The original RomM
  // accent colour; `primaryHover` and `primaryPressed` line up with v1's
  // `primary-lighten` / `primary-darken`.
  primary: "#8B74E8",
  primaryHover: "#A18FFF",
  primaryPressed: "#6043C8",
  // Secondary mirrors v1's secondary purple for chips / inactive bits.
  secondary: "#9E8CD6",
  secondaryHover: "#EBE7FA",
  secondaryPressed: "#7A6BB4",
  // Accent is v1's salmon/peach — used sparingly for emphasis.
  accent: "#E1A38D",
  accentHover: "#F0C8B8",
  // Favorite state — distinct from primary so a "selected" item and a
  // "favourite" item read differently.
  fav: "#FF4F6B",
  // User-avatar gradient picks up the primary palette so everything stays
  // in-family. (The mockup's red-to-magenta gradient is dropped here to
  // align with v1.)
  avatarGradient: "linear-gradient(135deg, #A18FFF, #6043C8)",
  // Legacy semantic colours available for specific chips / icons.
  rommRed: "#DA3633",
  rommGreen: "#3FB950",
  rommBlue: "#0070F3",
  rommGold: "#FFD700",
  // Light-theme brand variants (deeper for contrast on a light page).
  primaryLight: "#371F69",
  secondaryLight: "#553E98",
  primaryLightHover: "#7850E6",
  primaryLightPressed: "#452788",
  secondaryLightHover: "#F0EBFA",
  secondaryLightPressed: "#9B8BD0",
} as const;

export const colorStatus = {
  // Canonical status colours — used for solid surfaces (dialog buttons,
  // form errors, badges with solid background).
  success: "#4ADE80",
  warning: "#FBBF24",
  danger: "#FF5050",
  info: "#93C5FD",
  // Slightly-lighter foreground variants for text/icon when a status sits
  // on top of a tinted bg (e.g., success badge with green text on a 12%
  // green wash). For success and info the canonical colour already reads
  // well on the wash; warning and danger want a paler tone.
  warningFg: "#FACC15",
  dangerFg: "#F87171",
} as const;

// Solid hues used as the BASE for status-tinted backgrounds (the 12-30%
// wash behind success/warning/danger/info badges). Use via color-mix:
//   background: color-mix(in srgb, var(--r-color-status-success-base) 12%, transparent);
// These differ slightly from `colorStatus` on purpose — they're closer to
// tailwind's 500-tier so the resulting tint has the right saturation.
export const colorStatusBase = {
  success: "#22C55E",
  warning: "#EAB308",
  danger: "#EF4444",
  info: "#3B82F6",
} as const;

// External metadata-provider brand colours. Each provider (IGDB,
// MobyGames, ScreenScraper…) has its own brand identity; we replicate
// it on the corresponding chip / link so users recognise the source at
// a glance. Not theme-flippable: the provider's colour is what it is.
export const colorProvider = {
  igdb: "#6366F1",
  moby: "#F59E0B",
  screenscraper: "#3B82F6",
  retroachievements: "#EF4444",
  steamgriddb: "#0EA5E9",
  launchbox: "#8B5CF6",
  hasheous: "#6B7280",
  flashpoint: "#F97316",
  hltb: "#22C55E",
} as const;

// Dark (default) palette — the mockup is dark-only, so light uses an
// inverted alpha scheme that still reads as translucent glass.
export const colorDark = {
  bg: "#07070f",
  bgElevated: "rgba(255, 255, 255, 0.045)",
  surface: "rgba(255, 255, 255, 0.07)",
  surfaceHover: "rgba(255, 255, 255, 0.12)",
  fg: "#ffffff",
  fgSecondary: "rgba(255, 255, 255, 0.75)",
  fgMuted: "rgba(255, 255, 255, 0.45)",
  fgFaint: "rgba(255, 255, 255, 0.25)",
  border: "rgba(255, 255, 255, 0.07)",
  borderStrong: "rgba(255, 255, 255, 0.15)",
  // Used by global.css to draw the focus ring; translucent over dark surfaces.
  focus: "rgba(255, 255, 255, 0.45)",
  // Distinctive deep glass for menu/dialog panels — paired with --r-color-panel-border.
  panel: "rgba(16, 12, 28, 0.97)",
  panelBorder: "rgba(255, 255, 255, 0.1)",
  // Tooltip surface — slightly more opaque than panel so floating chips read clearly.
  tooltipBg: "rgba(7, 7, 15, 0.94)",
  tooltipBorder: "rgba(255, 255, 255, 0.09)",
  // Skeleton shimmer sweep — the translucent band that animates across .r-skeleton.
  shimmerSweep: "rgba(255, 255, 255, 0.08)",
  // Cover/media placeholder — dark glass behind missing artwork. Stays dark
  // in both themes because covers are media surfaces, not page surfaces.
  coverPlaceholder: "#1a1a2e",
  // Lighter shimmer-cycle tone for the placeholder loading animation.
  coverPlaceholderBright: "#252540",
  // Auth-card glass tone — fixed deep-blue glass that reads on the
  // background art regardless of theme.
  authGlass: "rgba(13, 17, 23, 0.65)",
  // Toast/notification background — opaque deep card.
  toastBg: "rgba(13, 17, 23, 0.92)",
} as const;

export const colorLight = {
  bg: "#f5f5fa",
  bgElevated: "rgba(0, 0, 0, 0.045)",
  surface: "rgba(0, 0, 0, 0.07)",
  surfaceHover: "rgba(0, 0, 0, 0.12)",
  fg: "#111117",
  fgSecondary: "rgba(17, 17, 23, 0.75)",
  fgMuted: "rgba(17, 17, 23, 0.45)",
  fgFaint: "rgba(17, 17, 23, 0.25)",
  border: "rgba(0, 0, 0, 0.07)",
  borderStrong: "rgba(0, 0, 0, 0.15)",
  focus: "rgba(0, 0, 0, 0.45)",
  panel: "rgba(255, 255, 255, 0.97)",
  panelBorder: "rgba(17, 17, 23, 0.1)",
  tooltipBg: "rgba(245, 245, 250, 0.96)",
  tooltipBorder: "rgba(17, 17, 23, 0.08)",
  shimmerSweep: "rgba(0, 0, 0, 0.06)",
  // Cover/media placeholder — same dark as colorDark.coverPlaceholder.
  // Cover artwork space stays dark in light mode too — bright covers need
  // dark backing.
  coverPlaceholder: "#1a1a2e",
  coverPlaceholderBright: "#252540",
  authGlass: "rgba(245, 245, 250, 0.85)",
  toastBg: "rgba(245, 245, 250, 0.95)",
} as const;

// Cover-overlay surfaces — fixed dark glass values that never theme-flip.
// These are used by surfaces sitting on top of cover artwork
// (GameCard chrome, GameActionBtn) where contrast against cover art matters
// more than page theme. Inverting them in light mode would lose contrast
// against bright covers.
export const colorOverlay = {
  fg: "rgba(255, 255, 255, 0.95)",
  fgSecondary: "rgba(255, 255, 255, 0.85)",
  fgMuted: "rgba(255, 255, 255, 0.45)",
  border: "rgba(255, 255, 255, 0.12)",
  borderStrong: "rgba(255, 255, 255, 0.25)",
  scrimSoft: "rgba(0, 0, 0, 0.55)",
  scrimStrong: "rgba(0, 0, 0, 0.78)",
  // Emphasis pill — fixed white-on-dark CTA (Play). Always solid white
  // regardless of page theme so it pops against any cover artwork.
  emphasisBg: "#ffffff",
  emphasisBgHover: "#e6e6e6",
  emphasisFg: "#111117",
} as const;

// Player canvas — full-black background for emulator/player surfaces.
// Independent of page theme; players draw over a true-black canvas.
export const colorCanvas = {
  bg: "#000000",
  bgDeep: "#0d1117",
} as const;

export const fontFamily = {
  sans: "'Segoe UI', -apple-system, BlinkMacSystemFont, system-ui, 'Inter', Roboto, sans-serif",
  display:
    "'Segoe UI', -apple-system, BlinkMacSystemFont, system-ui, 'Inter', Roboto, sans-serif",
  mono: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace",
} as const;

// Mockup-derived sizes lean small/dense — most body text sits around 13px.
export const fontSize = {
  xs: "10.5px",
  sm: "11.5px",
  md: "13px",
  lg: "14.5px",
  xl: "17px",
  "2xl": "22px",
  "3xl": "32px",
  "4xl": "38px",
} as const;

export const lineHeight = {
  tight: "1.1",
  normal: "1.4",
  relaxed: "1.7",
} as const;

export const fontWeight = {
  regular: "400",
  medium: "500",
  semibold: "600",
  bold: "700",
  extrabold: "800",
} as const;

// 4px base, with the mockup's more generous "row-pad" at the top end.
export const space = {
  0: "0",
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  7: "28px",
  8: "32px",
  10: "40px",
  12: "48px",
  14: "56px",
  rowPad: "36px",
} as const;

// Radii: `pill` = fully-rounded for buttons/chips/nav, `art` = card art
// (8px), `card` = surface cards (10-14px), `chip` = small tags (4-6px).
export const radius = {
  none: "0",
  xs: "3px",
  sm: "4px",
  chip: "6px",
  md: "8px",
  art: "8px",
  lg: "10px",
  card: "14px",
  xl: "20px",
  pill: "100px",
  full: "9999px",
} as const;

// Elevations match the mockup's single-source-of-truth drop shadows on
// cards and menus. Background blur lives on its own layer, not here.
export const elevation = {
  0: "none",
  1: "0 2px 8px rgba(0, 0, 0, 0.2)",
  2: "0 8px 24px rgba(0, 0, 0, 0.45)",
  3: "0 8px 30px rgba(0, 0, 0, 0.6)",
  4: "0 20px 60px rgba(0, 0, 0, 0.7)",
  5: "0 32px 96px rgba(0, 0, 0, 0.7)",
  cover: "0 24px 48px rgba(0, 0, 0, 0.8)",
} as const;

export const motion = {
  fast: "150ms",
  med: "220ms",
  slow: "360ms",
  easeOut: "cubic-bezier(0.22, 1, 0.36, 1)",
  easeInOut: "cubic-bezier(0.65, 0, 0.35, 1)",
} as const;

export const focus = {
  ringWidthMouse: "2px",
  ringWidthKey: "2.5px",
  ringWidthPad: "3.5px",
  ringOffset: "3px",
} as const;

// Layout constants from the mockup.
export const layout = {
  navHeight: "58px",
  rowPad: "36px",
  // Cap for the centred page content (navbar, game details body, …) on
  // ultrawide displays. Below this width the rule is a no-op.
  pageMaxWidth: "1500px",
  cardArtWidth: "158px",
  cardArtHeight: "213px",
  heroCardWidth: "300px",
  heroCardHeight: "169px",
  detailCoverWidth: "240px",
  // List-mode (table) gallery geometry. `GameListRow`, `GameListHeader`
  // and `GameListSkeletonRow` all derive their pixel sizing from these,
  // and `useGalleryVirtualItems` reads `listRowHeight` so the virtualiser's
  // exact-offset math stays in lock-step with the rendered CSS.
  listRowHeight: "80px",
  listHeaderHeight: "40px",
  listCoverWidth: "48px",
  listCoverHeight: "64px",
} as const;

export const tokens = {
  colorBrand,
  colorStatus,
  colorStatusBase,
  colorProvider,
  colorDark,
  colorLight,
  colorOverlay,
  colorCanvas,
  fontFamily,
  fontSize,
  lineHeight,
  fontWeight,
  space,
  radius,
  elevation,
  motion,
  focus,
  layout,
} as const;

export type Tokens = typeof tokens;
