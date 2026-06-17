// useGlobalHotkeys — app-wide keyboard shortcuts. Kept intentionally
// narrow so it doesn't fight with input fields or rich-text editors.
//
// Current bindings:
//   /   → navigate to /search (convention borrowed from Reddit / GitHub)
//   ?   → navigate to /search (shift-/, same behaviour)
//   g h → home
//   g p → platforms index
//   g c → collections index
//
// Two-key sequences (Gmail-style) have a 1.2s idle timeout. Everything is
// guarded against input fields and contenteditable.
import { onBeforeUnmount } from "vue";
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";

let installed = false;

function isEditable(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  if (
    el.tagName === "INPUT" ||
    el.tagName === "TEXTAREA" ||
    el.tagName === "SELECT"
  ) {
    return true;
  }
  return el.isContentEditable;
}

export function useGlobalHotkeys() {
  function install() {
    if (installed) return;
    if (typeof window === "undefined") return;
    installed = true;

    const router = useRouter();
    let pendingPrefix: string | null = null;
    let pendingAt = 0;
    const PREFIX_IDLE_MS = 1200;

    function onKey(e: KeyboardEvent) {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (isEditable(e.target)) return;

      const now = performance.now();
      if (pendingPrefix && now - pendingAt > PREFIX_IDLE_MS) {
        pendingPrefix = null;
      }

      // Slash / ? — jump to search.
      if ((e.key === "/" || e.key === "?") && !pendingPrefix) {
        router.push({ name: ROUTES.SEARCH });
        e.preventDefault();
        return;
      }

      // Two-key "g" prefix sequences.
      if (e.key === "g" && !pendingPrefix) {
        pendingPrefix = "g";
        pendingAt = now;
        return;
      }
      if (pendingPrefix === "g") {
        pendingPrefix = null;
        if (e.key === "h") {
          router.push({ name: ROUTES.HOME });
          e.preventDefault();
        } else if (e.key === "p") {
          router.push({ name: ROUTES.PLATFORMS_INDEX });
          e.preventDefault();
        } else if (e.key === "c") {
          router.push({ name: ROUTES.COLLECTIONS_INDEX });
          e.preventDefault();
        }
      }
    }

    window.addEventListener("keydown", onKey);

    onBeforeUnmount(() => {
      window.removeEventListener("keydown", onKey);
      installed = false;
    });
  }

  return { install };
}
