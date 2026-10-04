// useDeviceSaveSync: a web player's saves as this browser's sync device, from
// the launch through polled pushes to the page going away.
import { useEventListener, useIntervalFn } from "@vueuse/core";
import { useI18n } from "vue-i18n";
import storeAuth from "@/stores/auth";
import { useConfirm } from "@/v2/composables/useConfirm";
import {
  DeviceSaveSync,
  PLAYER_SAVE_POLL_MS,
  type LocalSave,
  type PlayerSaveFile,
  type SaveSyncRom,
} from "@/v2/utils/saveSync";
import { createRetryBackoff } from "@/v2/utils/saveSync/retryBackoff";

export interface DeviceSaveSyncOptions {
  emulator: string;
  /**
   * Reads what the player holds; given, pushes capture it first and can poll.
   *
   * Args:
   *   leaving: True when the player is quitting, which cannot wait a poll.
   */
  read?: (leaving: boolean) => Promise<PlayerSaveFile[]>;
  /** Reads what the player holds as the page goes away, which allows no await. */
  readOnUnload?: () => PlayerSaveFile[];
  pollMs?: number;
}

export function useDeviceSaveSync({
  emulator,
  read,
  readOnUnload,
  pollMs = PLAYER_SAVE_POLL_MS,
}: DeviceSaveSyncOptions) {
  const authStore = storeAuth();
  const confirm = useConfirm();
  const { t } = useI18n();

  let prepared: DeviceSaveSync | null = null;
  let sync: DeviceSaveSync | null = null;
  let pushing: Promise<boolean> | null = null;
  const retry = createRetryBackoff();

  /**
   * Sync a rom's saves ahead of its launch; `start` then puts them in play.
   *
   * Returns:
   *   The saves to hand the player, or null with no one signed in.
   */
  async function prepare(
    rom: SaveSyncRom,
    existing: PlayerSaveFile[] = [],
  ): Promise<LocalSave[] | null> {
    const userId = authStore.user?.id;
    if (userId == null) return null;
    const next = new DeviceSaveSync(rom, userId, emulator);
    const saves = await next.prepare(existing);
    prepared = next;
    return saves;
  }

  function run(polled: boolean): Promise<boolean> {
    const active = sync;
    if (!active) return Promise.resolve(true);
    if (!read) return active.push();
    // A push still in flight already covers this one's work.
    pushing ??= read(!polled)
      .then((files) => active.capture(files))
      .then(async () => {
        // A failing upload waits out its backoff; polls keep reading meanwhile.
        if (polled && !retry.ready()) return false;
        const pushed = await active.push();
        if (pushed) retry.reset();
        else retry.failed();
        return pushed;
      })
      .catch((error: unknown) => {
        console.error(`[Save sync] ${emulator} push failed`, error);
        retry.failed();
        return false;
      })
      .finally(() => {
        pushing = null;
      });
    return pushing;
  }

  /** Upload what changed; false when it failed and stays for the next push. */
  function push(): Promise<boolean> {
    return run(false);
  }

  // A push in flight may have read the saves before the latest one landed.
  async function flush(): Promise<boolean> {
    await pushing;
    return push();
  }

  const poll = useIntervalFn(() => void run(true), pollMs, {
    immediate: false,
  });

  function resume() {
    if (sync && read) poll.resume();
  }

  function start() {
    retry.reset();
    sync = prepared;
    prepared = null;
    resume();
  }

  function stop() {
    poll.pause();
    prepared = null;
    sync = null;
  }

  /** Keep what the player wrote, for the next push. */
  async function capture(files: PlayerSaveFile[]): Promise<void> {
    await sync?.capture(files);
  }

  function confirmDiscard(): Promise<boolean> {
    return confirm({
      title: t("play.quit-before-save-synced"),
      confirmText: t("common.discard"),
      cancelText: t("common.cancel"),
      tone: "danger",
    });
  }

  useEventListener(window, "pagehide", (event: PageTransitionEvent) => {
    if (!sync) return;
    if (!readOnUnload) return sync.pushOnUnload();
    // A page kept for back and forward can return to the running game.
    if (!event.persisted) sync.captureOnUnload(readOnUnload());
  });

  return {
    prepare,
    start,
    stop,
    push,
    flush,
    capture,
    pause: poll.pause,
    resume,
    confirmDiscard,
    isActive: () => sync !== null,
  };
}
