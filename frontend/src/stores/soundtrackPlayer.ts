import { useLocalStorage } from "@vueuse/core";
import { throttle } from "lodash";
import { defineStore } from "pinia";
import { computed, ref, shallowRef } from "vue";

const volumeStorage = useLocalStorage<number>("soundtrack.volume", 1);
const mutedStorage = useLocalStorage<boolean>("soundtrack.muted", false);

export interface PlayerTrack {
  romId: number;
  fileId: number;
  fileName: string;
  url: string;
}

export interface PlayerMeta {
  title?: string;
  artist?: string;
  album?: string;
  year?: string;
  genre?: string;
  track?: string;
  disc?: string;
  duration?: number;
  coverUrl?: string;
  folderCoverUrl?: string;
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

  function loadPlaylistForRom(
    romId: number,
    tracks: PlayerTrack[],
    metas: Record<number, PlayerMeta>,
  ) {
    playlist.value = tracks;
    playlistMeta.value = metas;
    activePlaylistRomId.value = romId;
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
    playlistMeta.value = {};
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
    setPlaying,
    setBuffering,
    setDuration,
    setError,
    next,
    previous,
    loadPlaylistForRom,
    reportCurrentTime,
  };
});

export default useSoundtrackPlayer;
