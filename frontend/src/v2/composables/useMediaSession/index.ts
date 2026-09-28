// Mirrors the soundtrack player into the Media Session API, so media keys, OS
// media overlays and lock screens show and control the playing track.
import { computed, onScopeDispose, watch } from "vue";
import useSoundtrackPlayer from "@/stores/soundtrackPlayer";
import { playerCoverUrl } from "@/v2/utils/soundtrackTracks";

const DEFAULT_SEEK_OFFSET_SECONDS = 10;

type HandledAction = Extract<
  MediaSessionAction,
  | "play"
  | "pause"
  | "stop"
  | "previoustrack"
  | "nexttrack"
  | "seekto"
  | "seekbackward"
  | "seekforward"
>;

// Registered only while the queue has a track in that direction.
const QUEUE_ACTIONS = new Set<HandledAction>(["previoustrack", "nexttrack"]);

function mediaSession(): MediaSession | null {
  return typeof navigator !== "undefined" && "mediaSession" in navigator
    ? navigator.mediaSession
    : null;
}

// Browsers throw for actions they don't support.
function setHandler(
  session: MediaSession,
  action: MediaSessionAction,
  handler: MediaSessionActionHandler | null,
) {
  try {
    session.setActionHandler(action, handler);
  } catch {
    // unsupported action
  }
}

function setPosition(session: MediaSession, state?: MediaPositionState) {
  if (typeof session.setPositionState !== "function") return;
  try {
    session.setPositionState(state);
  } catch {
    // rejected position state
  }
}

export function useMediaSession(): void {
  const session = mediaSession();
  if (!session) return;

  const store = useSoundtrackPlayer();

  function playOrPause(playing: boolean) {
    if (store.track && store.isPlaying !== playing) store.togglePlayPause();
  }

  function seekBy(offset: number) {
    const target = store.currentTime + offset;
    const max = store.duration > 0 ? store.duration : Infinity;
    store.seek(Math.min(max, Math.max(0, target)));
  }

  const handlers: Record<HandledAction, MediaSessionActionHandler> = {
    play: () => playOrPause(true),
    pause: () => playOrPause(false),
    stop: () => store.stop(),
    previoustrack: () => store.previous(),
    nexttrack: () => store.next(),
    seekto: (details) => {
      if (details.seekTime != null) store.seek(details.seekTime);
    },
    seekbackward: (details) =>
      seekBy(-(details.seekOffset ?? DEFAULT_SEEK_OFFSET_SECONDS)),
    seekforward: (details) =>
      seekBy(details.seekOffset ?? DEFAULT_SEEK_OFFSET_SECONDS),
  };

  const actions = Object.keys(handlers) as HandledAction[];
  for (const action of actions) {
    if (!QUEUE_ACTIONS.has(action)) {
      setHandler(session, action, handlers[action]);
    }
  }

  watch(
    () => store.hasPrevious,
    (has) =>
      setHandler(session, "previoustrack", has ? handlers.previoustrack : null),
    { immediate: true },
  );
  watch(
    () => store.hasNext,
    (has) => setHandler(session, "nexttrack", has ? handlers.nexttrack : null),
    { immediate: true },
  );

  const metadata = computed<MediaMetadataInit | null>(() => {
    if (!store.track) return null;
    return {
      title: store.meta.title || store.track.fileName,
      artist: store.meta.artist,
      album: store.meta.album,
      artwork: [{ src: playerCoverUrl(store.meta) }],
    };
  });

  watch(
    metadata,
    (init) => {
      session.metadata =
        init && typeof MediaMetadata !== "undefined"
          ? new MediaMetadata(init)
          : null;
    },
    { immediate: true },
  );

  watch(
    () => (store.track ? (store.isPlaying ? "playing" : "paused") : "none"),
    (state) => {
      session.playbackState = state;
    },
    { immediate: true },
  );

  watch(
    () => [store.track, store.duration, store.currentTime] as const,
    ([track, duration, position]) => {
      if (!track || !Number.isFinite(duration) || duration <= 0) {
        setPosition(session);
        return;
      }
      setPosition(session, {
        duration,
        position: Number.isFinite(position)
          ? Math.min(duration, Math.max(0, position))
          : 0,
      });
    },
    { immediate: true },
  );

  onScopeDispose(() => {
    for (const action of actions) setHandler(session, action, null);
    session.metadata = null;
    session.playbackState = "none";
    setPosition(session);
  });
}
