// romStatus — shared vocabulary for the ROM play-status picker (icons,
// enum/flag groupings). Consumed by the per-ROM status menu
// (`GameActionBtn`) and the bulk status menu (`SelectionBar`) so both
// surfaces present the same options, in the same order, with the same
// icons. v2-only: v1 still reads `romStatusMap`'s emoji from
// `@/utils`, so that map stays untouched.
import type { RomUserSchema, RomUserStatus } from "@/__generated__";
import type { PlayingStatus } from "@/utils";

// Advance a ROM's per-user status for a launch. Mutates in place so the
// caller can persist the same object it already sends to the props endpoint.
// The game becomes "now playing"; an empty or "finished" status rewinds to
// "incomplete" (they're playing again). Statuses the user set on purpose
// (completed 100% / retired / never playing) are left untouched.
export function applyLaunchStatus(romUser: RomUserSchema): void {
  romUser.now_playing = true;
  if (romUser.status === null || romUser.status === "finished") {
    romUser.status = "incomplete";
  }
}

// Icon map covering both the enum statuses and the orthogonal boolean
// flags (now_playing / backlogged / hidden) so a single menu can present
// them together.
export const STATUS_ICONS: Record<PlayingStatus, string> = {
  incomplete: "mdi-progress-clock",
  finished: "mdi-flag-checkered",
  completed_100: "mdi-trophy-outline",
  retired: "mdi-flag-off-outline",
  never_playing: "mdi-cancel",
  now_playing: "mdi-gamepad-variant",
  backlogged: "mdi-clock-outline",
  hidden: "mdi-eye-off-outline",
};

// The dashed-circle "no status set yet" placeholder icon.
export const STATUS_EMPTY_ICON = "mdi-progress-helper";

// Enum statuses — single-pick (radio-like) on a single ROM.
export const ENUM_KEYS: RomUserStatus[] = [
  "incomplete",
  "finished",
  "completed_100",
  "retired",
  "never_playing",
];

export type StatusFlagKey = "now_playing" | "backlogged" | "hidden";

// Two groups: play-status flags (now_playing / backlogged) describe when
// the user intends to play; the visibility flag (hidden) controls whether
// the ROM shows up in the library at all. Different category, so they get
// their own divider in the status menu.
export const PLAY_FLAG_KEYS: StatusFlagKey[] = ["now_playing", "backlogged"];
export const VISIBILITY_FLAG_KEYS: StatusFlagKey[] = ["hidden"];
export const FLAG_KEYS: StatusFlagKey[] = [
  ...PLAY_FLAG_KEYS,
  ...VISIBILITY_FLAG_KEYS,
];
