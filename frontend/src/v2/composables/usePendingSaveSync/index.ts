// Hands the server saves the browser is still holding, from wherever the user
// is in the app. Doing it at launch instead would be too late: by then the
// player has already drawn its save picker, so the save would land behind the
// choice the user just made.
import { onScopeDispose, watch } from "vue";
import romApi from "@/services/api/rom";
import pendingSaveStore, { syncPendingSaves } from "@/services/pending-save";
import storePlaying from "@/stores/playing";
import storeRoms from "@/stores/roms";
import { useServerConnection } from "@/v2/composables/useServerConnection";

// Long enough that a server that is up but refusing the save is not hammered.
const RETRY_MS = 30_000;

export function installPendingSaveSync() {
  const playingStore = storePlaying();
  const romsStore = storeRoms();
  const { isOffline } = useServerConnection();

  let timer: ReturnType<typeof setTimeout> | null = null;
  let draining = false;

  function stopRetrying() {
    if (timer === null) return;
    clearTimeout(timer);
    timer = null;
  }

  // A save that just landed is one the open details view is showing stale.
  async function refresh(romIds: number[]) {
    const current = romsStore.currentRom?.id;
    if (!current || !romIds.includes(current)) return;
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
        await refresh(await syncPendingSaves());
      }
      stopRetrying();
      const queued = (await pendingSaveStore.list()).length > 0;
      if (queued) timer = setTimeout(() => void drain(), RETRY_MS);
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
