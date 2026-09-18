import { defineStore } from "pinia";
import { ref } from "vue";
import romApi from "@/services/api/rom";
import {
  cancelNative,
  fetchPlatformSupport,
  isNativeShell,
  launchNative,
  nativeErrorMessage,
  nativeShellVersion,
  onNativeLaunchState,
} from "@/services/native";
import storeConfig from "@/stores/config";
import type { SimpleRom } from "@/stores/roms";
import type {
  LaunchState,
  PlatformSupport,
  SaveSyncOutcome,
} from "@/types/rommNative";
import {
  getDownloadFileName,
  getDownloadPath,
  getSoleRomFile,
  getSupportedEJSCores,
  resolvePlatformSlug,
} from "@/utils";

export type { LaunchState, PlatformSupport } from "@/types/rommNative";

// ── Store ─────────────────────────────────────────────────────────────────────

/**
 * Native play through the RomM desktop shell: launching a ROM in a locally
 * installed emulator instead of an in-browser core.
 *
 * Shaped after the streaming store, so the per-platform getters are
 * synchronous: a Play button inside a virtualised gallery cannot await. The
 * answer is a property of the user's own machine, so it is never cached beyond
 * the session.
 */
export const useNativeStore = defineStore("native", () => {
  const configStore = storeConfig();

  /** Whether the page is running inside the shell at all. */
  const available = ref(isNativeShell());
  const shellVersion = ref(nativeShellVersion());

  // Null prototype: RomM keeps whatever slug a folder is named, so "constructor"
  // and "toString" are slugs like any other, and on a plain object they would
  // read as already answered and return an inherited value.
  const support = ref<Record<string, PlatformSupport>>(
    Object.create(null) as Record<string, PlatformSupport>,
  );

  /** The shell's last word on each launch, keyed by ROM id. */
  const launches = ref<Record<number, LaunchState>>({});
  /** What happened to a save around each launch, keyed by ROM id. Kept apart
   *  from `launches` because it is not about the launch: the game has finished,
   *  and the save outlives the state that reported it. */
  const syncs = ref<Record<number, SaveSyncOutcome>>({});
  /** Display names, so launch feedback can name a game the shell identifies
   *  only by id. */
  const names = ref<Record<number, string>>({});
  /** Held from the click until `launch()` settles, so a button reads as busy
   *  before the shell has said anything about the launch. */
  const starting = ref(new Set<number>());
  /** Bumped per ROM on every state the shell sends, so `launch()` can tell a
   *  rejection the shell has already explained from one it has not. */
  const stateCount = ref<Record<number, number>>({});
  /** ROMs whose launch this page cancelled. The shell has no cancelled status:
   *  it aborts the transfer, which fails the launch, so the failure it then
   *  reports is the cancel and must not be surfaced as one. */
  const cancelled = ref(new Set<number>());

  let unsubscribe: (() => void) | null = null;

  // ── Getters ────────────────────────────────────────────────────────────────

  function supportForPlatform(
    slug: string | null | undefined,
  ): PlatformSupport | null {
    if (!slug) return null;
    return support.value[slug.toLowerCase()] ?? null;
  }

  /** Whether the shell can launch this platform. An unprobed one reads as
   *  unsupported, so no affordance is ever offered on a guess. */
  function isSupportedPlatform(slug: string | null | undefined): boolean {
    return supportForPlatform(slug)?.supported === true;
  }

  /** What to call the emulator a launch would use, for any surface that names
   *  where the game runs. */
  function labelForPlatform(slug: string | null | undefined): string | null {
    return supportForPlatform(slug)?.emulator ?? null;
  }

  function launchStateFor(
    romId: number | null | undefined,
  ): LaunchState | null {
    if (romId == null) return null;
    return launches.value[romId] ?? null;
  }

  /** What the shell said about this ROM's save, or null when it has said
   *  nothing since the last launch began. */
  function syncFor(romId: number | null | undefined): SaveSyncOutcome | null {
    if (romId == null) return null;
    return syncs.value[romId] ?? null;
  }

  /** Whether a launch is still on its way to the emulator, and so still
   *  cancellable. A game that has started is the shell's business. */
  function isLaunching(romId: number | null | undefined): boolean {
    if (romId == null) return false;
    return (
      starting.value.has(romId) ||
      launches.value[romId]?.status === "downloading"
    );
  }

  function nameFor(romId: number): string {
    return names.value[romId] ?? "";
  }

  /** Whether a cancel is outstanding for this ROM. Answers once, so a later
   *  genuine failure for the same ROM still reports, and callers clear the mark
   *  on any other ending too: a cancel the shell never took must not silence
   *  the failure of a launch that went on running. */
  function consumeCancelled(romId: number): boolean {
    if (!cancelled.value.has(romId)) return false;
    cancelled.value.delete(romId);
    return true;
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  /** Start listening for launch progress. Idempotent, and a no-op without a
   *  shell to listen to. */
  function install(): void {
    if (unsubscribe) return;
    unsubscribe = onNativeLaunchState((state) => {
      stateCount.value = {
        ...stateCount.value,
        [state.romId]: (stateCount.value[state.romId] ?? 0) + 1,
      };
      // A save moving is not the launch moving. Filed on its own and returned
      // from, rather than folded into `launches`, so a sync landing mid-launch
      // cannot read as the launch having ended: the save pull happens after the
      // ROM is ready and before the emulator starts, and the launch states
      // around it still have to arrive.
      if (state.status === "sync") {
        if (state.sync) {
          syncs.value = { ...syncs.value, [state.romId]: state.sync };
        }
        return;
      }
      if (state.status !== "downloading") starting.value.delete(state.romId);
      if (cancelled.value.has(state.romId)) {
        // An aborted transfer is how a cancel the shell took comes back, so
        // that failure belongs to the cancel and the record it dropped stays
        // dropped.
        if (
          state.status === "failed" &&
          state.error?.code === "download-failed"
        )
          return;
        // Any other ending means the cancel never landed. The mark comes off
        // so the launch reports itself, rather than being silenced by a
        // cancellation that did not happen.
        if (state.status !== "downloading") cancelled.value.delete(state.romId);
      }
      launches.value = { ...launches.value, [state.romId]: state };
    });
  }

  /**
   * Ask the shell which of these platforms it can launch, and cache the
   * answers. Platforms already answered are skipped, so this can be called
   * again as the library grows. The cores come from the same EJS map the
   * in-browser Play button reads.
   *
   * Args:
   *   force: re-ask about platforms already answered, for when the machine
   *     itself may have changed. Answers are merged rather than cleared
   *     first, so an affordance does not blink out while the shell replies.
   */
  async function probe(
    slugs: string[],
    { force = false }: { force?: boolean } = {},
  ): Promise<void> {
    install();
    if (!available.value) return;

    const wanted = new Set(
      slugs
        .filter(Boolean)
        .map((slug) => slug.toLowerCase())
        .filter((slug) => force || !(slug in support.value)),
    );
    if (wanted.size === 0) return;

    const answers = await fetchPlatformSupport(
      [...wanted].map((slug) => ({
        platformSlug: slug,
        cores: getSupportedEJSCores(
          resolvePlatformSlug(slug, configStore.config),
        ),
      })),
    );
    const merged = Object.assign(
      Object.create(null) as Record<string, PlatformSupport>,
      support.value,
    );
    for (const [slug, answer] of Object.entries(answers)) {
      merged[slug.toLowerCase()] = answer;
    }
    support.value = merged;
  }

  /** The rom with its file entries, fetched when the copy in hand has none.
   *  `/api/roms` omits them unless asked (`with_files`), so a rom off a gallery
   *  card cannot say what the download endpoint will serve it as. */
  async function withRomFiles(rom: SimpleRom): Promise<SimpleRom> {
    if ((rom.files ?? []).length > 0) return rom;
    try {
      const { data } = await romApi.getRom({ romId: rom.id });
      return { ...rom, files: data.files };
    } catch (error) {
      console.error("[native] Could not read the rom's files:", error);
      return rom;
    }
  }

  /** Hand a ROM to the shell to launch, resolving with an error message only
   *  when the shell never took the request (no bridge, a malformed request, a
   *  game already running). A launch it accepted and then failed is left to
   *  the launch state, whose error code every shell version reports. */
  async function launch(rom: SimpleRom): Promise<string | null> {
    const before = stateCount.value[rom.id] ?? 0;
    // A fresh launch is not the cancelled one, however the last ended.
    cancelled.value.delete(rom.id);
    // Nor does it carry the last launch's save outcome: a view watching for the
    // next one must not be sent to the old one on the way in.
    const { [rom.id]: _synced, ...withoutSync } = syncs.value;
    syncs.value = withoutSync;
    starting.value.add(rom.id);
    names.value = {
      ...names.value,
      [rom.id]: rom.name ?? rom.fs_name_no_ext,
    };
    // A gallery list is fetched without file entries, so a card's rom has none
    // and both helpers below would answer from the rom's own name. Fetched
    // rather than guessed.
    const detailed = await withRomFiles(rom);
    // `fs_name` is the served name for an ordinary single-file rom, but a
    // nested one is served as the file inside it, so without the entries there
    // is nothing to name the download and the shell would cache it under a name
    // no emulator opens. Better to say so than to launch something broken.
    if ((detailed.files ?? []).length === 0 && rom.has_nested_single_file) {
      starting.value.delete(rom.id);
      return "The rom's files could not be read.";
    }
    // Passthrough needs one real file to point at, which a rom served as a
    // built-on-request archive does not have.
    const soleFile = getSoleRomFile(detailed);
    try {
      await launchNative({
        romId: rom.id,
        downloadPath: getDownloadPath({ rom: detailed }),
        // What the endpoint will actually serve, which for a folder rom is
        // neither `fs_name` nor `fs_name` with an extension.
        fileName: getDownloadFileName(detailed),
        platformSlug: rom.platform_slug,
        cores: getSupportedEJSCores(
          resolvePlatformSlug(rom.platform_slug, configStore.config),
        ),
        name: rom.name ?? undefined,
        // Lets a shell on the same machine as the server play the file where it
        // already is. A shell without library-passthrough downloads instead.
        ...(soleFile
          ? {
              serverPath: soleFile.full_path,
              fileSize: soleFile.file_size_bytes,
            }
          : {}),
      });
      return null;
    } catch (error) {
      if ((stateCount.value[rom.id] ?? 0) > before) return null;
      return nativeErrorMessage(error);
    } finally {
      starting.value.delete(rom.id);
    }
  }

  /** Ask the shell to abort a launch, answering whether the request reached it.
   *  Delivery is not acceptance: the shell returns silently when the emulator
   *  has already started, so the mark this leaves only claims a cancellation
   *  once an aborted transfer actually arrives (see `consumeCancelled`). */
  async function cancel(romId: number): Promise<boolean> {
    if (!(await cancelNative(romId))) return false;
    cancelled.value.add(romId);
    starting.value.delete(romId);
    // The shell acknowledges a cancel by dropping the launch rather than by
    // reporting a state for it, so the record has to go from here.
    const { [romId]: _dropped, ...rest } = launches.value;
    launches.value = rest;
    return true;
  }

  return {
    available,
    shellVersion,
    // Exposed for a caller that builds a function inside a computed and needs
    // it rebuilt when the probe lands, the way streaming exposes its config.
    support,
    supportForPlatform,
    isSupportedPlatform,
    labelForPlatform,
    launchStateFor,
    syncFor,
    isLaunching,
    nameFor,
    consumeCancelled,
    install,
    probe,
    launch,
    cancel,
  };
});
