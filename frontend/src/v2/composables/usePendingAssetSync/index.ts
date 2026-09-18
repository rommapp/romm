// Hands the server what the browser still holds, from anywhere in the app: at
// launch the picker is already drawn, so it would land behind the user's pick.
import { uniqBy } from "lodash";
import { onScopeDispose, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  hasPendingAssets,
  syncPendingAssets,
  type DroppedAsset,
  type PendingAssetKind,
  type SyncedAsset,
} from "@/services/pending-asset";
import storePlaying from "@/stores/playing";
import storeRoms from "@/stores/roms";
import { useRomSync } from "@/v2/composables/useRomSync";
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
  return uniqBy(assets, (asset) => `${asset.kind}:${asset.romId}`);
}

// Two shells must not both be draining the same rows into the same server.
let draining = false;

export function installPendingAssetSync() {
  const playingStore = storePlaying();
  const romsStore = storeRoms();
  const snackbar = useSnackbar();
  const { t } = useI18n();
  const { isOffline } = useServerConnection();
  const { refetchRom } = useRomSync();

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

  // The progress is gone from the browser, so the player is told why.
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
    if (current && synced.some((asset) => asset.romId === current)) {
      await refetchRom(current);
    }
  }

  async function drain() {
    // Offline nothing gets through, and reconnecting starts a pass of its own.
    if (draining || isOffline.value) return;
    draining = true;
    try {
      // A running session retries its own save, and a version opened from
      // under it is one it would not know about; a state nothing else hands over.
      const kinds: PendingAssetKind[] = playingStore.playing
        ? ["state"]
        : ["save", "state"];
      const { synced, dropped } = await syncPendingAssets(kinds);
      announce(synced);
      reportRefused(dropped);
      await refresh(synced);
      stopRetrying();
      // The shell can go while a pass is on the wire, and a retry armed after
      // that would outlive it and keep firing for the life of the document.
      if (!disposed && (await hasPendingAssets(kinds))) {
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
