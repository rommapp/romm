// Saves the soundtrack player's queue and position on this device and restores
// it after a reload, while the user's `resumeMusic` setting is on.
import {
  useEventListener,
  useLocalStorage,
  watchDebounced,
  whenever,
} from "@vueuse/core";
import { storeToRefs } from "pinia";
import { onMounted, watch } from "vue";
import { useUISettings } from "@/composables/useUISettings";
import storeAuth from "@/stores/auth";
import useSoundtrackPlayer, {
  type SoundtrackSession,
} from "@/stores/soundtrackPlayer";

export const SOUNDTRACK_SESSION_KEY = "soundtrack.session";

interface StoredSession {
  userId: number;
  session: SoundtrackSession;
}

function isStoredSession(value: unknown): value is StoredSession {
  const stored = value as Partial<StoredSession> | null;
  const session = stored?.session;
  return (
    typeof stored?.userId === "number" &&
    typeof session?.track?.url === "string" &&
    Array.isArray(session.playlist) &&
    Array.isArray(session.originalPlaylist) &&
    typeof session.position === "number"
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

  const saved = useLocalStorage<StoredSession | null>(
    SOUNDTRACK_SESSION_KEY,
    null,
    {
      writeDefaults: false,
      // A save from "pagehide" has to land before the page unloads.
      flush: "sync",
      serializer: { read: readStoredSession, write: JSON.stringify },
    },
  );

  function save() {
    const userId = authStore.user?.id;
    if (!resumeMusic.value || userId === undefined) return;
    saved.value = session.value ? { userId, session: session.value } : null;
  }

  // Restored only once the player's `<audio>` exists and the user is known,
  // so a session never resumes for someone else signing in on this device.
  onMounted(() => {
    whenever(
      () => authStore.user?.id,
      (userId) => {
        const stored = saved.value;
        if (resumeMusic.value && stored?.userId === userId && !player.track) {
          player.restore(stored.session);
        }
      },
      { immediate: true, once: true },
    );
  });

  watchDebounced(session, save, { debounce: 1000, maxWait: 5000 });
  useEventListener(window, "pagehide", save);
  watch(resumeMusic, (enabled) => {
    if (enabled) save();
    else saved.value = null;
  });
}
