// Hands the server saves and states the browser is still holding, from
// wherever the user is in the app. Doing it at launch instead would be too
// late: by then the player has already drawn its picker, so the asset would
// land behind the choice the user just made.
import { onScopeDispose, watch } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import {
  hasPendingAssets,
  syncPendingAssets,
  type DroppedAsset,
  type PendingAssetKind,
  type SyncedAsset,
} from "@/services/pending-asset";
import storePlaying from "@/stores/playing";
import storeRoms from "@/stores/roms";
import { useServerConnection } from "@/v2/composables/useServerConnection";
import { useSnackbar } from "@/v2/composables/useSnackbar";

// Long enough that a server that is up but refusing the upload is not hammered.
const RETRY_MS = 30_000;

const SYNCED_MESSAGE: Record<PendingAssetKind, string> = {
  save: "play.last-save-synced",
  state: "play.last-state-synced",
};

const REFUSED_MESSAGE: Record<PendingAssetKind, string> = {
  save: "play.save-sync-refused",
  state: "play.state-sync-refused",
};

// A session that queued several captures owes the player one line per game,
// not one per capture.
function firstPerGame<T extends SyncedAsset>(assets: T[]): T[] {
  const seen = new Set<string>();
  const first: T[] = [];
  for (const asset of assets) {
    const key = `${asset.kind}:${asset.romId}`;
    if (seen.has(key)) continue;
    seen.add(key);
    first.push(asset);
  }
  return first;
}

// Two shells must not both be draining the same rows into the same server.
let draining = false;

export function installPendingAssetSync() {
  const playingStore = storePlaying();
  const romsStore = storeRoms();
  const snackbar = useSnackbar();
  const { t } = useI18n();
  const { isOffline } = useServerConnection();

  let timer: ReturnType<typeof setTimeout> | null = null;
  let disposed = false;

  function stopRetrying() {
    if (timer === null) return;
    clearTimeout(timer);
    timer = null;
  }

  function announce(synced: SyncedAsset[]) {
    for (const asset of firstPerGame(synced)) {
      snackbar.success(t(SYNCED_MESSAGE[asset.kind], { game: asset.name }), {
        image: asset.cover,
        timeout: 5000,
      });
    }
  }

  // The progress is gone from the browser, so the player is told why rather
  // than left waiting for a sync that will never come.
  function reportRefused(dropped: DroppedAsset[]) {
    for (const asset of firstPerGame(dropped)) {
      snackbar.error(
        t(REFUSED_MESSAGE[asset.kind], {
          game: asset.name,
          reason: asset.reason,
        }),
        { image: asset.cover, timeout: 10000 },
      );
    }
  }

  // An asset that just landed is one the open details view is showing stale.
  async function refresh(synced: SyncedAsset[]) {
    const current = romsStore.currentRom?.id;
    if (!current || !synced.some((asset) => asset.romId === current)) return;
    try {
      const { data } = await romApi.getRom({ romId: current });
      romsStore.setCurrentRom(data);
    } catch (error) {
      console.error(
        "Failed to refresh a rom after a pending asset synced",
        error,
      );
    }
  }

  async function drain() {
    if (draining) return;
    draining = true;
    try {
      // A running session retries its own save every second, and a version
      // opened from under it is one it would not know about. A state is a
      // finished capture, and nothing else is going to hand it over.
      const kinds: PendingAssetKind[] = playingStore.playing
        ? ["state"]
        : ["save", "state"];
      if (!isOffline.value) {
        const { synced, dropped } = await syncPendingAssets(kinds);
        announce(synced);
        reportRefused(dropped);
        await refresh(synced);
      }
      stopRetrying();
      // The shell can go while a pass is on the wire, and a retry armed after
      // that would outlive it and keep firing for the life of the document.
      if (!disposed && (await hasPendingAssets())) {
        timer = setTimeout(() => void drain(), RETRY_MS);
      }
    } finally {
      draining = false;
    }
  }

  // Quitting a game is what queues an asset, and reconnecting is what lets it
  // through, so both are worth another attempt.
  watch([() => playingStore.playing, isOffline], () => void drain(), {
    immediate: true,
  });
  onScopeDispose(() => {
    disposed = true;
    stopRetrying();
  });
}
