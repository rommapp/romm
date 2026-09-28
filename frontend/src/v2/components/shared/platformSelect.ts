import { sortBy, partition } from "lodash";
import type { Platform } from "@/stores/platforms";

/** `rom_count > 0` first, then empty; each block sorted by `display_name`. */
export const promotePlatformsWithGamesFirst = <
  T extends Pick<Platform, "rom_count" | "display_name">,
>(
  platforms: T[],
): { promoted: T[]; remaining: T[] } => {
  const [promoted, remaining] = partition(
    sortBy(platforms, (p) => p.display_name),
    (p) => p.rom_count > 0,
  );
  return { promoted, remaining };
};

export const PLATFORM_ROM_COUNT_CAP = 9999;

/** Display rom count in platform picker rows; caps at `9999+`. */
export function formatPlatformRomCount(count: number): string {
  if (count > PLATFORM_ROM_COUNT_CAP) return `${PLATFORM_ROM_COUNT_CAP}+`;
  return String(count);
}
