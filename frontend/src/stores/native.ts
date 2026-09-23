import { defineStore } from "pinia";
import { ref } from "vue";
import romApi from "@/services/api/rom";
import {
  canLaunchFullscreen,
  canPickDisc,
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
import type { DiscSelection } from "@/v2/utils/playerDisc";

export type { LaunchState, PlatformSupport } from "@/types/rommNative";

/** What the play page has already settled about a session. Every field is
 *  optional: a gallery card with no panel behind it asks for none of it. */
export interface NativeLaunchChoice {
  /** The core to try first. A name the shell cannot find is one it installs, so
   *  this is honoured even for a core the machine has never had. */
  core?: string | null;
  /** Whether to start the emulator fullscreen. Undefined asks for nothing,
   *  leaving the emulator's own configuration to decide. */
  fullscreen?: boolean;
  /** Which file of a multi-disc rom to boot, or ALL_DISCS for the whole set.
   *  Null and undefined both ask for nothing, which boots the set whole. */
  disc?: DiscSelection;
}

// ── Store ─────────────────────────────────────────────────────────────────────

/** Native play through the RomM desktop shell. The getters answer synchronously
 *  and are never cached beyond the session: they describe the user's machine. */
export const useNativeStore = defineStore("native", () => {
  const configStore = storeConfig();

  /** Whether the page is running inside the shell at all. */
  const available = ref(isNativeShell());
  const shellVersion = ref(nativeShellVersion());
  /** Whether a native launch takes the page's full-screen choice with it.
   *  Read once, like the two above: the bridge is injected before the app
   *  boots and a shell cannot gain a capability while its page is open. */
  const honoursFullscreen = ref(canLaunchFullscreen());
  /** Whether a launch takes the page's disc choice with it. Read once, like
   *  the others: a shell cannot gain a capability while its page is open. */
  const honoursDisc = ref(canPickDisc());

  // Null prototype: RomM keeps whatever slug a folder is named, so "constructor"
  // and "toString" are slugs like any other, and on a plain object they would
  // read as already answered and return an inherited value.
  const support = ref<Record<string, PlatformSupport>>(
    Object.create(null) as Record<string, PlatformSupport>,
  );
  // The probe that asked about each slug last, so an answer cannot outlive the
  // request that superseded it: a focus re-probe overlaps the probe still in
  // flight from mount, and the shell's answer changes between them.
  let probeSeq = 0;
  const askedAt = new Map<string, number>();

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

  /** Whether a cancel is outstanding for this ROM, answered once so a genuine
   *  failure later still reports. Any other ending clears the mark. */
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
      // A save moving is not the launch moving: filed apart and returned from,
      // so a sync landing mid-launch cannot read as the launch having ended.
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

  /** Ask the shell which of these platforms it can launch, and cache the
   *  answers. Merged rather than cleared, so an affordance never blinks out.
   *
   * Args:
   *   force: re-ask about platforms already answered, for when the machine
   *     itself may have changed.
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

    const seq = ++probeSeq;
    for (const slug of wanted) askedAt.set(slug, seq);
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
      const key = slug.toLowerCase();
      // A slug a later probe has since asked about belongs to that probe.
      if (askedAt.get(key) !== seq) continue;
      merged[key] = answer;
    }
    support.value = merged;
  }

  /** The platform's cores with the page's choice at the front, named once. A
   *  core the platform map does not list is still honoured: the page offered
   *  it, and the shell's own preferences outrank this list anyway. */
  function coresFor(rom: SimpleRom, chosen?: string | null): string[] {
    const supported = getSupportedEJSCores(
      resolvePlatformSlug(rom.platform_slug, configStore.config),
    );
    if (!chosen) return supported;
    return [chosen, ...supported.filter((core) => core !== chosen)];
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

  /** Hand a ROM to the shell to launch, resolving with an error only when the
   *  shell never took the request: a launch it accepted and then failed is left
   *  to the launch state.
   *
   * Args:
   *   choice: what the play page has already asked the user, so a native launch
   *     honours the same answers as the in-browser one.
   */
  async function launch(
    rom: SimpleRom,
    choice: NativeLaunchChoice = {},
  ): Promise<string | null> {
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
    // A nested rom is served as the file inside it, so without the entries there
    // is nothing to name the download and the shell caches an unopenable name.
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
        // The page's core first: the shell installs the first candidate it
        // cannot find, so the rest are there for a core that is not published.
        cores: coresFor(rom, choice.core),
        name: rom.name ?? undefined,
        // Sent whatever the shell advertises: an older one drops an unknown
        // field and starts the emulator as its own config says, which is
        // where it was before the page could ask.
        ...(choice.fullscreen === undefined
          ? {}
          : { fullscreen: choice.fullscreen }),
        // A rom with one file has no disc to pick, so the page's answer for it
        // is not one to send: the shell would look for a disc set and find a
        // single file, which is the launch it performs anyway.
        ...(choice.disc == null ? {} : { disc: choice.disc }),
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
   *  Delivery is not acceptance: the mark lands when the transfer aborts. */
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
    honoursFullscreen,
    honoursDisc,
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
