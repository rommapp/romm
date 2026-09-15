import { onScopeDispose, toValue, watch, type MaybeRefOrGetter } from "vue";
import storePlaying from "@/stores/playing";

/** Mirrors a player's running state into the global stage flag that
 *  unmounts the app chrome and zeroes the nav-height tokens. */
export function useStageActive(running: MaybeRefOrGetter<boolean>): void {
  const playingStore = storePlaying();
  // Deliberately not the `playing` flag: that one also spans pre-stage
  // phases (Stream sets it while loading behind its config screen).
  watch(
    () => toValue(running),
    (active) => playingStore.setStageActive(active),
    { immediate: true },
  );
  onScopeDispose(() => playingStore.setStageActive(false));
}

/** Mirrors the flag onto <html> (next to the theme classes) so
 *  body-teleported overlays resolve the zeroed nav-height tokens too. */
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
