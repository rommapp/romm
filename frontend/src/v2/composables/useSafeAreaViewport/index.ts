import { useMediaQuery } from "@vueuse/core";
import { onScopeDispose, watch } from "vue";
import storePlaying from "@/stores/playing";

const COVER = "viewport-fit=cover";

function setCover(on: boolean): void {
  const meta = document.querySelector<HTMLMetaElement>('meta[name="viewport"]');
  if (!meta) return;
  const parts = meta.content
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part && !part.startsWith("viewport-fit"));
  if (on) parts.push(COVER);
  meta.content = parts.join(", ");
}

/** Draws the page under a phone's status bar in portrait, where the top bar
 *  pads itself by the inset; landscape and a running player stay off the notch. */
export function installSafeAreaViewport(): void {
  const portrait = useMediaQuery("(orientation: portrait)");
  const playingStore = storePlaying();
  watch(() => portrait.value && !playingStore.stageActive, setCover, {
    immediate: true,
  });
  onScopeDispose(() => setCover(false));
}
