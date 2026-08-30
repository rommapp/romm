import { useLocalStorage } from "@vueuse/core";
import { throttle } from "lodash";
import { defineStore } from "pinia";
import { computed, ref, shallowRef } from "vue";
import type { TrackMetaSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH, isCDBasedSystem, shuffled } from "@/utils";

const volumeStorage = useLocalStorage<number>("soundtrack.volume", 1);
const mutedStorage = useLocalStorage<boolean>("soundtrack.muted", false);

export interface PlayerTrack {
  romId: number;
  fileId: number;
  fileName: string;
  url: string;
}

// Audio-tag fields are sourced from the generated schema; the rest (duration in
// seconds + resolved cover URLs) are UI-specific to the player.
type AudioTagKey =
  "title" | "artist" | "album" | "year" | "genre" | "track" | "disc";

export type PlayerMeta = {
  [K in AudioTagKey]?: NonNullable<TrackMetaSchema[K]>;
} & {
  duration?: number;
  coverUrl?: string;
  folderCoverUrl?: string;
  gameArtworkUrl?: string;
};

export type SoundtrackArtworkRom = Pick<
  DetailedRom,
  | "ss_metadata"
  | "launchbox_metadata"
  | "platform_slug"
  | "path_cover_large"
  | "path_cover_small"
  | "url_cover"
>;

// LaunchBox image type depicting the physical disc.
const LAUNCHBOX_DISC_TYPE = "disc";

// LaunchBox media can be a `launchbox-file://` URI pointing at the server's
// local LaunchBox folder, which the browser cannot load.
function isBrowserLoadable(url: string): boolean {
  return /^https?:\/\//i.test(url) || url.startsWith("/");
}

function launchboxDiscArtwork(rom: SoundtrackArtworkRom): string | undefined {
  return rom.launchbox_metadata?.images?.find(
    (image) =>
      (image.type ?? "").trim().toLowerCase() === LAUNCHBOX_DISC_TYPE &&
      isBrowserLoadable(image.url),
  )?.url;
}

export function resolveSoundtrackGameArtwork(
  rom: SoundtrackArtworkRom,
): string | undefined {
  // A disc scan reads as album art, so it outranks the logo on CD systems.
  if (isCDBasedSystem(rom.platform_slug)) {
    const physicalPath = rom.ss_metadata?.physical_path;
    if (physicalPath) return `${FRONTEND_RESOURCES_PATH}/${physicalPath}`;

    const discUrl = launchboxDiscArtwork(rom);
    if (discUrl) return discUrl;
  }

  const logoPath = rom.ss_metadata?.logo_path;
  if (logoPath) return `${FRONTEND_RESOURCES_PATH}/${logoPath}`;

  return (
    rom.path_cover_large ?? rom.path_cover_small ?? rom.url_cover ?? undefined
  );
}

const useSoundtrackPlayer = defineStore("soundtrackPlayer", () => {
  const track = ref<PlayerTrack | null>(null);
  const meta = ref<PlayerMeta>({});
  const isPlaying = ref(false);
  const isBuffering = ref(false);
  const hasError = ref(false);
  const currentTime = ref(0);
  const duration = ref(0);
  const audioRef = shallowRef<HTMLAudioElement | null>(null);
  const volume = volumeStorage;
  const muted = mutedStorage;
  const playlist = ref<PlayerTrack[]>([]);
  const originalPlaylist = ref<PlayerTrack[]>([]);
  const isShuffled = ref(false);
  const playlistMeta = ref<Record<number, PlayerMeta>>({});
  const activePlaylistRomId = ref<number | null>(null);

  function setAudioRef(el: HTMLAudioElement | null) {
    audioRef.value = el;
    if (el) {
      el.volume = volume.value;
      el.muted = muted.value;
    }
  }

  function setVolume(v: number) {
    volume.value = Math.min(1, Math.max(0, v));
    if (volume.value > 0 && muted.value) muted.value = false;
    const el = audioRef.value;
    if (el) {
      el.volume = volume.value;
      el.muted = muted.value;
    }
  }

  function toggleMute() {
    muted.value = !muted.value;
    const el = audioRef.value;
    if (el) el.muted = muted.value;
  }

  const setCurrentTimeThrottled = throttle(
    (t: number) => {
      currentTime.value = t;
    },
    200,
    { leading: true, trailing: true },
  );

  function reportCurrentTime(t: number) {
    setCurrentTimeThrottled(t);
  }

  function setPlaying(v: boolean) {
    isPlaying.value = v;
    if (v) hasError.value = false;
  }
  function setBuffering(v: boolean) {
    isBuffering.value = v;
  }
  function setDuration(d: number) {
    duration.value = Number.isFinite(d) && d >= 0 ? d : 0;
  }
  function setError() {
    hasError.value = true;
    isPlaying.value = false;
    isBuffering.value = false;
  }

  function loadPlaylist(
    tracks: PlayerTrack[],
    metas: Record<number, PlayerMeta>,
    romId: number | null = null,
    preserveShuffle = false,
  ) {
    const previousOrder = playlist.value;
    const wasShuffled = isShuffled.value;
    originalPlaylist.value = [...tracks];
    playlistMeta.value = metas;
    activePlaylistRomId.value = romId;

    if (preserveShuffle && wasShuffled) {
      const tracksByKey = new Map(
        tracks.map((item) => [item.romId + ":" + item.fileId, item]),
      );
      const restored = previousOrder.flatMap((item) => {
        const next = tracksByKey.get(item.romId + ":" + item.fileId);
        if (!next) return [];
        tracksByKey.delete(item.romId + ":" + item.fileId);
        return [next];
      });
      // Freshly paged-in tracks join shuffled too, or playback would turn
      // sequential once the already loaded window runs out.
      playlist.value =
        restored.length > 0
          ? [...restored, ...shuffled([...tracksByKey.values()])]
          : shuffled([...tracksByKey.values()]);
      return;
    }

    playlist.value = [...tracks];
    isShuffled.value = false;
  }

  function loadPlaylistForRom(
    romId: number,
    tracks: PlayerTrack[],
    metas: Record<number, PlayerMeta>,
  ) {
    loadPlaylist(tracks, metas, romId);
  }

  function toggleShuffle() {
    if (isShuffled.value) {
      playlist.value = [...originalPlaylist.value];
      isShuffled.value = false;
      return;
    }

    const current = track.value;
    const remaining = originalPlaylist.value.filter(
      (item) =>
        !current ||
        item.fileId !== current.fileId ||
        item.romId !== current.romId,
    );
    const shuffledRemaining = shuffled(remaining);
    playlist.value = current
      ? [current, ...shuffledRemaining]
      : shuffledRemaining;
    isShuffled.value = true;
  }

  function play(t: PlayerTrack, m: PlayerMeta) {
    // Drop any buffered time-update from the previous track so the slider
    // doesn't briefly snap to an old value before `timeupdate` fires.
    setCurrentTimeThrottled.cancel();
    track.value = t;
    meta.value = m;
    currentTime.value = 0;
    duration.value = m.duration ?? 0;
    isBuffering.value = true;
    hasError.value = false;
  }

  const currentIndex = computed(() => {
    if (!track.value) return -1;
    return playlist.value.findIndex(
      (p) => p.fileId === track.value!.fileId && p.romId === track.value!.romId,
    );
  });

  const hasPrevious = computed(() => currentIndex.value > 0);
  const hasNext = computed(
    () =>
      currentIndex.value >= 0 && currentIndex.value < playlist.value.length - 1,
  );

  function next() {
    if (!hasNext.value) return;
    const nextTrack = playlist.value[currentIndex.value + 1];
    play(nextTrack, playlistMeta.value[nextTrack.fileId] ?? {});
  }

  function previous() {
    if (!hasPrevious.value) return;
    const prevTrack = playlist.value[currentIndex.value - 1];
    play(prevTrack, playlistMeta.value[prevTrack.fileId] ?? {});
  }

  function stop() {
    setCurrentTimeThrottled.cancel();
    const el = audioRef.value;
    if (el) {
      el.pause();
      el.removeAttribute("src");
      try {
        el.load();
      } catch {
        // ignore
      }
    }
    track.value = null;
    meta.value = {};
    isPlaying.value = false;
    isBuffering.value = false;
    hasError.value = false;
    currentTime.value = 0;
    duration.value = 0;
    playlist.value = [];
    originalPlaylist.value = [];
    playlistMeta.value = {};
    isShuffled.value = false;
    activePlaylistRomId.value = null;
  }

  function togglePlayPause() {
    const el = audioRef.value;
    if (!el) return;
    if (el.paused) {
      void el.play();
    } else {
      el.pause();
    }
  }

  function seek(t: number) {
    const el = audioRef.value;
    if (el && Number.isFinite(t)) el.currentTime = t;
  }

  return {
    track,
    meta,
    isPlaying,
    isBuffering,
    hasError,
    currentTime,
    duration,
    volume,
    muted,
    playlist,
    isShuffled,
    activePlaylistRomId,
    hasPrevious,
    hasNext,
    audioRef,
    setAudioRef,
    play,
    stop,
    togglePlayPause,
    seek,
    setVolume,
    toggleMute,
    toggleShuffle,
    setPlaying,
    setBuffering,
    setDuration,
    setError,
    next,
    previous,
    loadPlaylist,
    loadPlaylistForRom,
    reportCurrentTime,
  };
});

export default useSoundtrackPlayer;
