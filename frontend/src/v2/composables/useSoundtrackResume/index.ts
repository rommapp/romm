// Saves the soundtrack player's queue and position on this device and restores
// it after a reload, while the user's `resumeMusic` setting is on.
import { useEventListener, watchDebounced, whenever } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { onMounted, onScopeDispose, watch } from "vue";
import { useUISettings } from "@/composables/useUISettings";
import storeAuth from "@/stores/auth";
import useSoundtrackPlayer, {
  type PlayerTrack,
  type SoundtrackSession,
} from "@/stores/soundtrackPlayer";

export const SOUNDTRACK_SESSION_KEY = "soundtrack.session";
export const SOUNDTRACK_CHANNEL = "romm-jukebox";
export const PLAYING_REPLY_TIMEOUT_MS = 200;

interface StoredSession {
  userId: number;
  session: SoundtrackSession;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isTrack(value: unknown): value is PlayerTrack {
  const t = value as Partial<PlayerTrack> | null;
  return (
    typeof t?.romId === "number" &&
    typeof t.fileId === "number" &&
    typeof t.fileName === "string" &&
    typeof t.url === "string"
  );
}

function isTrackList(value: unknown): value is PlayerTrack[] {
  return Array.isArray(value) && value.every(isTrack);
}

function isStoredSession(value: unknown): value is StoredSession {
  const stored = value as Partial<StoredSession> | null;
  const session = stored?.session;
  return (
    typeof stored?.userId === "number" &&
    isTrack(session?.track) &&
    isRecord(session.meta) &&
    isTrackList(session.playlist) &&
    isTrackList(session.originalPlaylist) &&
    isRecord(session.playlistMeta) &&
    typeof session.isShuffled === "boolean" &&
    (session.activePlaylistRomId === null ||
      typeof session.activePlaylistRomId === "number") &&
    typeof session.position === "number" &&
    typeof session.wasPlaying === "boolean"
  );
}

// Anything unreadable fails safe to "nothing saved".
export function readStoredSession(raw: string): StoredSession | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    return isStoredSession(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

// Asks the other open tabs whether one is playing, so a session doesn't play
// twice. A tab that closed, crashed or is reloading can't answer.
function isPlayingElsewhere(
  channel: BroadcastChannel | null,
): Promise<boolean> {
  if (!channel) return Promise.resolve(false);
  return new Promise((resolve) => {
    const done = (playing: boolean) => {
      clearTimeout(timer);
      channel.removeEventListener("message", onMessage);
      resolve(playing);
    };
    const onMessage = (event: MessageEvent) => {
      if (event.data === "playing") done(true);
    };
    const timer = setTimeout(() => done(false), PLAYING_REPLY_TIMEOUT_MS);
    channel.addEventListener("message", onMessage);
    channel.postMessage("ask");
  });
}

export function useSoundtrackResume() {
  const { resumeMusic } = useUISettings();
  const player = useSoundtrackPlayer();
  const { session } = storeToRefs(player);
  const authStore = storeAuth();
  const channel =
    typeof BroadcastChannel === "undefined"
      ? null
      : new BroadcastChannel(SOUNDTRACK_CHANNEL);
  useEventListener(channel, "message", (event: MessageEvent) => {
    if (event.data === "ask" && player.isPlaying) {
      channel?.postMessage("playing");
    }
  });
  onScopeDispose(() => channel?.close());

  function write(stored: StoredSession | null) {
    try {
      if (stored) {
        localStorage.setItem(SOUNDTRACK_SESSION_KEY, JSON.stringify(stored));
      } else {
        localStorage.removeItem(SOUNDTRACK_SESSION_KEY);
      }
    } catch {
      // Storage full or unavailable: the session just won't resume.
    }
  }

  // Only this tab's own changes are saved, so a tab that restored a session or
  // sat idle never overwrites the one another tab is playing.
  let unsaved = false;
  const watched = () => (resumeMusic.value ? session.value : null);
  watch(watched, () => (unsaved = true), { flush: "sync" });

  function save() {
    unsaved = false;
    const userId = authStore.user?.id;
    if (!resumeMusic.value || userId === undefined) return;
    write(session.value ? { userId, session: session.value } : null);
  }

  // Restored once the player's `<audio>` exists, on each sign-in, so a session
  // never resumes for someone else signing in on this device.
  onMounted(() => {
    whenever(
      () => authStore.user?.id,
      async (userId) => {
        const stored = readStoredSession(
          localStorage.getItem(SOUNDTRACK_SESSION_KEY) ?? "",
        );
        if (!resumeMusic.value || stored?.userId !== userId || player.track) {
          return;
        }
        const { session: saved } = stored;
        const elsewhere =
          saved.wasPlaying && (await isPlayingElsewhere(channel));
        if (player.track || authStore.user?.id !== userId) return;
        player.restore({
          ...saved,
          wasPlaying: saved.wasPlaying && !elsewhere,
        });
      },
      { immediate: true },
    );
  });

  function saveChanges() {
    if (unsaved && !player.pendingResume) save();
  }

  watchDebounced(watched, saveChanges, { debounce: 1000, maxWait: 5000 });
  useEventListener(window, "pagehide", saveChanges);
  watch(resumeMusic, (enabled) => {
    if (enabled) save();
    else write(null);
  });
}
