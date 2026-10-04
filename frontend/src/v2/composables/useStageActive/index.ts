import { onScopeDispose, toValue, watch, type MaybeRefOrGetter } from "vue";
import storePlaying from "@/stores/playing";

// Mirrors a source into one of the playing store's flags, cleared on dispose.
function mirrorFlag(
  source: MaybeRefOrGetter<boolean>,
  set: (on: boolean) => void,
): void {
  watch(() => toValue(source), set, { immediate: true });
  onScopeDispose(() => set(false));
}

/** Mirrors a player's running state into the global stage flag that
 *  unmounts the app chrome and collapses the nav-height tokens. */
export function useStageActive(running: MaybeRefOrGetter<boolean>): void {
  const playingStore = storePlaying();
  // Deliberately not the `playing` flag: that one also spans pre-stage
  // phases (Stream sets it while loading behind its config screen).
  mirrorFlag(running, (on) => playingStore.setStageActive(on));
}

/** Mirrors a session, launch or pending claim included, into the global
 *  playing flag, which hands the controller from useGamepad to the session. */
export function usePlayingWhile(active: MaybeRefOrGetter<boolean>): void {
  const playingStore = storePlaying();
  mirrorFlag(active, (on) => playingStore.setPlaying(on));
}

/** Mirrors the flag onto <html> (next to the theme classes) so
 *  body-teleported overlays resolve the collapsed nav-height tokens too. */
export function installStageActiveClass(): void {
  const playingStore = storePlaying();
  watch(
    () => playingStore.stageActive,
    (active) => {
      document.documentElement.classList.toggle("r-v2-stage-active", active);
    },
    { immediate: true },
  );
  onScopeDispose(() =>
    document.documentElement.classList.remove("r-v2-stage-active"),
  );
}
