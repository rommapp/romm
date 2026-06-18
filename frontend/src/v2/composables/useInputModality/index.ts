// useInputModality
//
// Tracks the user's last-used input device and exposes it as a reactive ref.
// Writes `data-input` on <html> so CSS can adapt focus rings, hit targets,
// and hint visibility per modality. A single shared instance is enough —
// install() from the root layout mounts listeners once.
import { onBeforeUnmount, readonly, ref } from "vue";

export type InputModality = "mouse" | "touch" | "key" | "pad";

const modality = ref<InputModality>("mouse");
let installed = false;

function applyAttribute(next: InputModality) {
  if (typeof document === "undefined") return;
  document.documentElement.dataset.input = next;
}

function setModality(next: InputModality) {
  if (modality.value === next) return;
  modality.value = next;
  applyAttribute(next);
}

export function useInputModality() {
  function install() {
    if (installed) return;
    installed = true;

    applyAttribute(modality.value);

    // Mouse handlers — split because, once the user is on a gamepad,
    // we want the mouse to "disappear": tiny accidental nudges of a
    // couch-side mouse shouldn't paint hover states on top of the
    // focused tile. Only a deliberate click (mousedown) flips the
    // modality back to mouse; mousemove / wheel are ignored while
    // in pad mode.
    const onMouseMove = () => {
      if (modality.value === "pad") return;
      setModality("mouse");
    };
    const onMouseDown = () => setModality("mouse");
    const onWheel = () => {
      if (modality.value === "pad") return;
      setModality("mouse");
    };
    const onTouch = () => setModality("touch");
    const onKey = (e: KeyboardEvent) => {
      // Ignore modifier-only presses and clicks that happen to be keyboard-
      // triggered — what we care about is real navigational keys.
      if (
        e.key === "Tab" ||
        e.key.startsWith("Arrow") ||
        e.key === "Enter" ||
        e.key === " " ||
        e.key === "Escape"
      ) {
        setModality("key");
      }
    };
    // A gamepad connection is a strong signal the user is on a pad. Real
    // per-button detection happens when we port the console input bus; until
    // then we flip to "pad" on connect and stay there until another input
    // type takes over.
    const onGamepad = () => setModality("pad");

    window.addEventListener("mousemove", onMouseMove, { passive: true });
    window.addEventListener("mousedown", onMouseDown, { passive: true });
    window.addEventListener("wheel", onWheel, { passive: true });
    window.addEventListener("touchstart", onTouch, { passive: true });
    window.addEventListener("keydown", onKey);
    window.addEventListener("gamepadconnected", onGamepad);

    onBeforeUnmount(() => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("touchstart", onTouch);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("gamepadconnected", onGamepad);
      installed = false;
    });
  }

  return {
    modality: readonly(modality),
    install,
    setModality,
  };
}
