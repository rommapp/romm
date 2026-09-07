// The core a game is played with is remembered twice: under the game, and
// under its platform as the default for every other game on that platform.
const gameKey = (romId: number) => `player:${romId}:core`;
const platformKey = (platformSlug: string) => `player:${platformSlug}:core`;

/**
 * The first remembered core the platform still supports, else its first core.
 *
 * Each candidate is validated so a core that is no longer offered (renamed
 * upstream, or gated behind netplay) falls through instead of masking the next.
 */
export function resolveRememberedCore(
  romId: number,
  platformSlug: string,
  supportedCores: readonly string[],
): string {
  return (
    [
      localStorage.getItem(gameKey(romId)),
      localStorage.getItem(platformKey(platformSlug)),
    ].find((core): core is string => !!core && supportedCores.includes(core)) ??
    supportedCores[0]
  );
}

/** Remember `core` for the game and its platform, or forget both when null. */
export function rememberCore(
  romId: number,
  platformSlug: string,
  core: string | null,
): void {
  for (const key of [gameKey(romId), platformKey(platformSlug)]) {
    if (core) localStorage.setItem(key, core);
    else localStorage.removeItem(key);
  }
}
