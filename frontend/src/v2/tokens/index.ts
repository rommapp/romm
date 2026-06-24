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
} as const;

// Light-theme brand overrides. The brand palette above is tuned for dark
// surfaces and cover-art overlays, where the lighter purples pop. On the
// off-white light page those same hues wash out (primary lands near 3:1,
// the salmon accent and light-purple links worse), so light mode deepens
// primary, secondary and accent to clear AA for brand-coloured text, links,
// active-nav and chips. These keys share the brand CSS names, so the build
// emits them inside .r-v2-light and they override the shared values there.
// Hover/pressed deepen further (a light page gains emphasis by going darker,
// the inverse of dark mode where hover goes lighter).
export const colorBrandLight = {
  primary: "#553E98",
  primaryHover: "#452788",
  primaryPressed: "#371F69",
  secondary: "#6E5CA8",
  accent: "#A85530",
  // Rating stars (RRating) read as bright neon gold on dark; on the light
  // page that washes out, so deepen to a darkgoldenrod that still reads
  // unmistakably as gold.
  rommGold: "#B8860B",
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

// Light-theme status overrides. The canonical status colours above are
// tuned bright for dark surfaces; on the off-white page the neon green,
// yellow and pale blue wash out (a green play-badge or a yellow rating
// star barely registers). Light mode drops them ~one Tailwind tier deeper
// so each still reads as its hue (icons, badges, solid buttons) on white.
// Emitted into .r-v2-light with the same CSS names, so they override the
// shared values there.
export const colorStatusLight = {
  success: "#15A34A",
  // One tier brighter than a naive deepening (yellow-600, not -700) so the
  // rating metric's gold star reads as vivid as the danger-red difficulty
  // icon beside it, instead of a muddy olive. warningFg (text-on-wash) stays
  // deep.
  warning: "#CA8A04",
  danger: "#DC2626",
  info: "#2563EB",
  warningFg: "#854D0E",
  dangerFg: "#B91C1C",
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
  // Page-title heading ink. Pure white on dark needs no softening; the light
  // theme overrides this to a slightly-muted near-black (white-on-dark titles
  // don't read as harshly as black-on-white ones).
  fgHeading: "#ffffff",
  fgSecondary: "rgba(255, 255, 255, 0.75)",
  fgMuted: "rgba(255, 255, 255, 0.45)",
  fgFaint: "rgba(255, 255, 255, 0.25)",
  fgFaintHard: "rgba(255, 255, 255, 0.05)",
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
  // RSwitch ON knob — dark ink that pops on the bright dark-theme track.
  switchKnobOn: "#111117",
} as const;

export const colorLight = {
  bg: "#f5f5fa",
  // Text and borders run stronger than a naive inversion of dark (muted/faint
  // at <0.45 disappear on the off-white page), but the surface FILLS stay
  // light: translucent-black panels read as muddy grey on a light page, so
  // keep their alpha low and lean on borders + shadow for separation. Hover
  // still darkens enough to register as feedback.
  bgElevated: "rgba(0, 0, 0, 0.025)",
  surface: "rgba(0, 0, 0, 0.035)",
  surfaceHover: "rgba(0, 0, 0, 0.1)",
  fg: "#111117",
  // Large bold page titles in pure near-black read harsh on the off-white
  // page; soften them a touch while body text stays at full `fg`.
  fgHeading: "rgba(17, 17, 23, 0.86)",
  fgSecondary: "rgba(17, 17, 23, 0.82)",
  fgMuted: "rgba(17, 17, 23, 0.74)",
  fgFaint: "rgba(17, 17, 23, 0.58)",
  border: "rgba(0, 0, 0, 0.1)",
  borderStrong: "rgba(0, 0, 0, 0.22)",
  focus: "rgba(0, 0, 0, 0.45)",
  // Menus / selects / dialogs. Pure white popped hard against the faintly
  // lavender page; sit just a hair above the bg tone instead and rely on the
  // shadow + panel-border for separation, so overlays read as lifted rather
  // than as stark white cards.
  panel: "rgba(240, 240, 246, 0.98)",
  panelBorder: "rgba(17, 17, 23, 0.1)",
  tooltipBg: "rgba(245, 245, 250, 0.96)",
  tooltipBorder: "rgba(17, 17, 23, 0.08)",
  shimmerSweep: "rgba(0, 0, 0, 0.06)",
  // Cover/media placeholder — the backing shown behind artwork while the
  // image loads (and the shimmer skeleton tone). Theme-aware: a dark box
  // under a loading card reads as out-of-place on the light page, so light
  // mode uses a soft lavender-grey, a hair darker than the bg so the card
  // still reads as a filled surface. The procedural "no cover" SVG art
  // (colorCoverArt) is separate and keeps its own purple/peach regardless.
  coverPlaceholder: "#e4e2ef",
  coverPlaceholderBright: "#efeef7",
  authGlass: "rgba(245, 245, 250, 0.85)",
  toastBg: "rgba(245, 245, 250, 0.95)",
  // RSwitch ON knob — white knob so it pops on light theme's deep-purple
  // track instead of sinking into it as a dark blob.
  switchKnobOn: "rgba(255, 255, 255, 0.95)",
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
  // Rating gold for badges sitting on the cover scrim (GameCard rating).
  // Stays bright in both themes: the scrim is always dark, so the deep
  // light-theme `romm-gold` (tuned for legibility on the light PAGE) would
  // sink into it. Page-context gold keeps using --r-color-romm-gold.
  gold: "#FFD700",
} as const;

// Player canvas — full-black background for emulator/player surfaces.
// Independent of page theme; players draw over a true-black canvas.
export const colorCanvas = {
  bg: "#000000",
  bgDeep: "#0d1117",
} as const;

// CRT gimmick — the cosmetic "CRT mode" shader + power-on warm-up flash
// (see CrtOverlay.vue / CrtWarmup.vue, toggled from Settings → User Interface → Theme).
// Theme-agnostic by design: the phosphor green and the red/cyan chromatic-aberration ghosts
// read the same on dark and light, so they live in SHARED rather than the
// per-theme palettes. Consumed only as CSS vars (--r-color-crt-*), always at
// low opacity via color-mix.
export const colorCrt = {
  // Phosphor afterglow / glow tint (P1 green).
  glow: "#7dffb4",
  // Chromatic-aberration ghosts for the RGB-split glitch.
  ghostWarm: "#ff3b5c",
  ghostCool: "#3bd9ff",
} as const;

// Procedural cover-art palette — the fixed colours of the generated
// "no cover" artwork (missing / unmatched placeholders). Baked into an
// SVG string by `utils/covers`, so they live here as the single home for
// these literals (zero-hex policy) and never theme-flip — the art is the
// same purple/peach in dark and light. Consumed via the JS export, not as
// CSS vars.
export const colorCoverArt = {
  base: "#553E98", // backdrop
  shade: "#371F69", // dark blob
  warm: "#FF9B85", // peach blob
  icon: "#F9F9F9", // foreground icon
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
  // Back-out: slight overshoot at the end of the curve. Used for "juicy"
  // micro-interactions (chevron flip, sub-pill drop-in) where a touch of
  // bounce signals playfulness without going full cartoon.
  easeBack: "cubic-bezier(0.34, 1.56, 0.64, 1)",
} as const;

export const focus = {
  ringWidthMouse: "2px",
  ringWidthKey: "2.5px",
  ringWidthPad: "3.5px",
  ringOffset: "3px",
} as const;

// Stacking layers. Drawers sit BELOW dialogs so a dialog opened from
// within an RDrawer (e.g. SearchCoverDialog from CollectionSettingsDrawer)
// lands on top of the drawer's blur scrim instead of trapped behind it.
// Menus / dropdowns / popovers must sit ABOVE dialogs so that a select
// or date picker opened from within an RDialog isn't trapped behind the
// dialog surface. Tooltips ride above menus so a hover-help on a menu
// item is still legible. Snackbars cap the stack — nothing covers an
// active toast.
export const zIndex = {
  drawer: "2300",
  dialog: "2400",
  menu: "2500",
  tooltip: "2600",
  snackbar: "2700",
} as const;

// Layout constants from the mockup.
export const layout = {
  navHeight: "58px",
  // Fixed bottom tab bar shown on phones (xs). Mirrors navHeight so the
  // top and bottom chrome read as a matched pair. Consumed as
  // `--r-bottom-nav-h` to reserve space in AppLayout and offset the
  // gallery scroll height / MiniPlayer on mobile.
  bottomNavHeight: "58px",
  // Cap for the bottom tab bar pill so it stays thumb-sized on large
  // tablets (the sm range reaches 959px) instead of stretching the four
  // destinations edge-to-edge. Below this width the pill just fills the
  // available row; above it, it centres at this width.
  bottomNavMaxWidth: "480px",
  // Minimum comfortable hit-target on touch / gamepad (WCAG-ish 44px).
  // Interactive primitives bump small controls up to this on `xs` /
  // touch where the desktop sizing would be too tight for a thumb.
  touchTarget: "44px",
  rowPad: "36px",
  // Cap for the centred page content (navbar, game details body, …) on
  // ultrawide displays. Below this width the rule is a no-op.
  pageMaxWidth: "1920px",
  // Default ("md") card art geometry. The gallery grid reads
  // `--r-card-art-w` directly, so this stays the canonical size for
  // every untiered consumer. The size-tier values below are picked up
  // by `GameCard`'s `size` prop and override the default locally on
  // the card via CSS vars.
  cardArtWidth: "158px",
  cardArtHeight: "213px",
  // Card art size tiers. All maintain ratio ≈ 0.74 (boxart 2:3) so the
  // cover never visually distorts between sizes.
  //   xs (48 × 64)   — list-row avatars
  //   sm (120 × 162) — dense pickers, compact mobile
  //   md (158 × 213) — gallery default (== cardArtWidth / cardArtHeight)
  //   lg (200 × 270) — edit-dialog cover preview
  //   xl (240 × 324) — detail page cover column
  cardArtWidthXs: "48px",
  cardArtHeightXs: "64px",
  cardArtWidthSm: "120px",
  cardArtHeightSm: "162px",
  cardArtWidthLg: "200px",
  cardArtHeightLg: "270px",
  cardArtWidthXl: "240px",
  cardArtHeightXl: "324px",
  // Hero (16:9) variant — scales linearly with the card art tier so
  // `hero` reads as "wide aspect ratio at this size" instead of a
  // standalone fixed shape. md keeps the canonical 300 × 169.
  heroCardWidth: "300px",
  heroCardHeight: "169px",
  heroCardWidthXs: "90px",
  heroCardHeightXs: "51px",
  heroCardWidthSm: "230px",
  heroCardHeightSm: "130px",
  heroCardWidthLg: "380px",
  heroCardHeightLg: "214px",
  heroCardWidthXl: "460px",
  heroCardHeightXl: "259px",
  detailCoverWidth: "240px",
  // List-mode (table) gallery geometry. `GameListRow`, `GameListHeader`
  // and `GameListSkeletonRow` all derive their pixel sizing from these,
  // and `useGalleryVirtualItems` reads `listRowHeight` so the virtualiser's
  // exact-offset math stays in lock-step with the rendered CSS.
  // (The row thumb sizing now comes from `cardArtWidthXs / HeightXs` via
  // `<GameCard size="xs" />` — no dedicated list-cover token.)
  listRowHeight: "80px",
  listHeaderHeight: "40px",
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
  zIndex,
} as const;

export type Tokens = typeof tokens;
