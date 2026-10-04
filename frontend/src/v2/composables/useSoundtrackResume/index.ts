// Saves the soundtrack player's queue and position on this device and restores
// it after a reload, while the user's `resumeMusic` setting is on.
import { useEventListener, watchDebounced, whenever } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { onMounted, watch } from "vue";
import { useUISettings } from "@/composables/useUISettings";
import storeAuth from "@/stores/auth";
import useSoundtrackPlayer, {
  type PlayerTrack,
  type SoundtrackSession,
} from "@/stores/soundtrackPlayer";

export const SOUNDTRACK_SESSION_KEY = "soundtrack.session";

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

export function useSoundtrackResume() {
  const { resumeMusic } = useUISettings();
  const player = useSoundtrackPlayer();
  const { session } = storeToRefs(player);
  const authStore = storeAuth();

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

  function save() {
    const userId = authStore.user?.id;
    if (!resumeMusic.value || userId === undefined) return;
    write(session.value ? { userId, session: session.value } : null);
  }

  // Restored once the player's `<audio>` exists, on each sign-in, so a session
  // never resumes for someone else signing in on this device.
  onMounted(() => {
    whenever(
      () => authStore.user?.id,
      (userId) => {
        const stored = readStoredSession(
          localStorage.getItem(SOUNDTRACK_SESSION_KEY) ?? "",
        );
        if (resumeMusic.value && stored?.userId === userId && !player.track) {
          player.restore(stored.session);
        }
      },
      { immediate: true },
    );
  });

  watchDebounced(() => (resumeMusic.value ? session.value : null), save, {
    debounce: 1000,
    maxWait: 5000,
  });
  useEventListener(window, "pagehide", save);
  watch(resumeMusic, (enabled) => {
    if (enabled) save();
    else write(null);
  });
}
