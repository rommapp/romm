import type { ReleaseType } from "@/__generated__";

/** Every release type, in the order the backend's `ReleaseType` declares them. */
export const RELEASE_TYPES = [
  "homebrew",
  "hack",
  "color_patch",
  "translation",
  "fan_game",
  "total_conversion",
  "randomizer",
  "demake",
  "port",
  "prototype",
  "utility",
  "tech_demo",
  "unlicensed",
] as const satisfies readonly ReleaseType[];

// Fails to compile when the backend adds a type this list is missing.
type _Exhaustive =
  Exclude<ReleaseType, (typeof RELEASE_TYPES)[number]> extends never
    ? true
    : never;
const _exhaustive: _Exhaustive = true;
void _exhaustive;

export function releaseTypeLabelKey(value: string): string {
  return `rom.release-type-${value.replaceAll("_", "-")}`;
}
