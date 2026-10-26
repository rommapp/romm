import type { MusicTrackSchema } from "@/__generated__";
import { shuffled } from "@/utils";

export const FREE_RADIO_DURATION_SECONDS = 60 * 60;

export function buildFreeRadioSession(
  tracks: MusicTrackSchema[],
  random: () => number = Math.random,
): MusicTrackSchema[] {
  const eligibleTracks = tracks.filter(
    (track) =>
      typeof track.duration_seconds === "number" &&
      Number.isFinite(track.duration_seconds) &&
      track.duration_seconds > 0,
  );
  const byAlbum = new Map<number, MusicTrackSchema[]>();
  for (const track of eligibleTracks) {
    const albumTracks = byAlbum.get(track.rom_id) ?? [];
    albumTracks.push(track);
    byAlbum.set(track.rom_id, albumTracks);
  }

  const albumQueues = shuffled([...byAlbum.values()], random).map((album) =>
    shuffled(album, random),
  );
  const balancedOrder: MusicTrackSchema[] = [];
  while (albumQueues.some((album) => album.length > 0)) {
    for (const album of shuffled(albumQueues, random)) {
      const track = album.shift();
      if (track) balancedOrder.push(track);
    }
  }

  if (trackDurationSeconds(balancedOrder) <= FREE_RADIO_DURATION_SECONDS)
    return balancedOrder;

  const session: MusicTrackSchema[] = [];
  let sessionDuration = 0;
  for (const track of balancedOrder) {
    const duration = track.duration_seconds ?? 0;
    if (sessionDuration + duration > FREE_RADIO_DURATION_SECONDS) continue;
    session.push(track);
    sessionDuration += duration;
  }
  return session;
}

export function trackDurationSeconds(tracks: MusicTrackSchema[]): number {
  return tracks.reduce(
    (total, track) => total + (track.duration_seconds ?? 0),
    0,
  );
}
