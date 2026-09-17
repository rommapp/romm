// Hands the server saves the browser is still holding, from wherever the user
// is in the app. Doing it at launch instead would be too late: by then the
// player has already drawn its save picker, so the save would land behind the
// choice the user just made.
import { onScopeDispose, watch } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import {
  hasPendingSaves,
  syncPendingSaves,
  type SyncedSave,
} from "@/services/pending-save";
import storePlaying from "@/stores/playing";
import storeRoms from "@/stores/roms";
import { useServerConnection } from "@/v2/composables/useServerConnection";
import { useSnackbar } from "@/v2/composables/useSnackbar";

// Long enough that a server that is up but refusing the save is not hammered.
const RETRY_MS = 30_000;

// Two shells must not both be draining the same rows into the same server.
let draining = false;

export function installPendingSaveSync() {
  const playingStore = storePlaying();
  const romsStore = storeRoms();
  const snackbar = useSnackbar();
  const { t } = useI18n();
  const { isOffline } = useServerConnection();

  let timer: ReturnType<typeof setTimeout> | null = null;

  function stopRetrying() {
    if (timer === null) return;
    clearTimeout(timer);
    timer = null;
  }

  function announce(synced: SyncedSave[]) {
    for (const save of synced) {
      snackbar.success(t("play.last-save-synced", { game: save.name }), {
        image: save.cover,
        timeout: 5000,
      });
    }
  }

  // A save that just landed is one the open details view is showing stale.
  async function refresh(synced: SyncedSave[]) {
    const current = romsStore.currentRom?.id;
    if (!current || !synced.some((save) => save.romId === current)) return;
    try {
      const { data } = await romApi.getRom({ romId: current });
      romsStore.setCurrentRom(data);
    } catch (error) {
      console.error(
        "Failed to refresh a rom after a pending save synced",
        error,
      );
    }
  }

  async function drain() {
    if (draining) return;
    draining = true;
    try {
      // The player retries its own session every second while a game runs, and
      // a version opened from under it is one that session would not know about.
      if (!playingStore.playing && !isOffline.value) {
        const synced = await syncPendingSaves();
        announce(synced);
        await refresh(synced);
      }
      stopRetrying();
      if (await hasPendingSaves()) {
        timer = setTimeout(() => void drain(), RETRY_MS);
      }
    } finally {
      draining = false;
    }
  }

  // Quitting a game is what queues a save, and reconnecting is what lets it
  // through, so both are worth another attempt.
  watch([() => playingStore.playing, isOffline], () => void drain(), {
    immediate: true,
  });
  onScopeDispose(stopRetrying);
}
