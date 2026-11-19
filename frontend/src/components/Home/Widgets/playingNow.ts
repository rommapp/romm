import type { ActivityEntry } from "@/services/api/activity";

export interface PlayingNowPick {
  /** The longest-running session of the picked game; names its player. */
  lead: ActivityEntry;
  /** Distinct players on the picked game, including the lead. */
  playerCount: number;
  /** Distinct games being played besides the picked one. */
  otherGames: number;
}

function startedAt(entry: ActivityEntry): number {
  return new Date(entry.started_at).getTime();
}

/** The game with the most distinct users (a streaming session's twin entries
 *  count once), ties going to the longest-running one so the card stays put. */
export function pickPlayingNow(
  entries: readonly ActivityEntry[],
): PlayingNowPick | null {
  const byRom = new Map<number, ActivityEntry[]>();
  for (const entry of entries) {
    const group = byRom.get(entry.rom_id);
    if (group) group.push(entry);
    else byRom.set(entry.rom_id, [entry]);
  }

  let best: { lead: ActivityEntry; playerCount: number } | null = null;
  for (const group of byRom.values()) {
    const lead = group.reduce((a, b) => (startedAt(b) < startedAt(a) ? b : a));
    const playerCount = new Set(group.map((e) => e.user_id)).size;
    if (
      !best ||
      playerCount > best.playerCount ||
      (playerCount === best.playerCount &&
        startedAt(lead) < startedAt(best.lead))
    ) {
      best = { lead, playerCount };
    }
  }

  return best ? { ...best, otherGames: byRom.size - 1 } : null;
}
