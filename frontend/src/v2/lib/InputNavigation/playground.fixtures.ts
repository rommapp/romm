import { RTag } from "@v2/lib";
import {
  defineComponent,
  h,
  onBeforeUnmount,
  onMounted,
  ref,
  type PropType,
} from "vue";

/** Friendly "try this" panel at the top of a playground story. */
export const PlaygroundCallout = defineComponent({
  name: "PlaygroundCallout",
  props: {
    title: { type: String, required: true },
    keys: { type: Array as PropType<string[]>, default: () => [] },
  },
  setup(props, { slots }) {
    return () =>
      h("div", { role: "note", class: "pg-callout", style: CALLOUT_STYLE }, [
        h(
          "strong",
          { style: "font-size: 1.05rem; color: var(--r-color-fg)" },
          props.title,
        ),
        h(
          "p",
          { style: "margin: 0; color: var(--r-color-fg-secondary)" },
          slots.default?.(),
        ),
        props.keys.length
          ? h(
              "div",
              {
                style: "display: flex; gap: var(--r-space-2); flex-wrap: wrap",
              },
              props.keys.map((k) =>
                h(RTag, { key: k, text: k, mono: true, size: "small" }),
              ),
            )
          : null,
      ]);
  },
});

const CALLOUT_STYLE = [
  "display: grid",
  "gap: var(--r-space-2)",
  "padding: var(--r-space-4)",
  "border: 1px solid var(--r-color-border)",
  "border-radius: var(--r-radius-lg)",
  "background: var(--r-color-surface)",
  "max-width: 640px",
].join(";");

/** Label of the focused element's `data-label`, live. */
export function useFocusReadout() {
  const focused = ref("nothing");
  const update = () => {
    const el = document.activeElement as HTMLElement | null;
    focused.value = el?.dataset.label ?? "nothing";
  };
  onMounted(() => {
    document.addEventListener("focusin", update);
    document.addEventListener("focusout", update);
  });
  onBeforeUnmount(() => {
    document.removeEventListener("focusin", update);
    document.removeEventListener("focusout", update);
  });
  return focused;
}

/** Dispatches a keydown on the focused element and returns it, so a play can read defaultPrevented. */
export function pressKey(key: string): KeyboardEvent {
  const event = new KeyboardEvent("keydown", {
    key,
    bubbles: true,
    cancelable: true,
  });
  (document.activeElement ?? document.body).dispatchEvent(event);
  return event;
}

export function byLabel(root: HTMLElement, label: string): HTMLElement {
  const el = root.querySelector<HTMLElement>(`[data-label="${label}"]`);
  if (!el) throw new Error(`No element with data-label="${label}"`);
  return el;
}

export function labels(prefix: string, count: number): string[] {
  return Array.from({ length: count }, (_, i) => `${prefix} ${i + 1}`);
}
