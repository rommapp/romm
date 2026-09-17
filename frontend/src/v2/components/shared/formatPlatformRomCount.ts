export const PLATFORM_ROM_COUNT_CAP = 9999;

/** Display rom count in platform picker rows; caps at `9999+`. */
export function formatPlatformRomCount(count: number): string {
  if (count > PLATFORM_ROM_COUNT_CAP) return `${PLATFORM_ROM_COUNT_CAP}+`;
  return String(count);
}
