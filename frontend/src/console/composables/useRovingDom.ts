import { watch, type Ref } from "vue";

interface RovingOptions {
  scroll?: boolean; // default true
  block?: ScrollLogicalPosition; // vertical alignment
  inline?: ScrollLogicalPosition; // horizontal alignment
  behavior?: ScrollBehavior; // smooth vs auto
  focus?: boolean; // default true
}

export function useRovingDom(
  index: Ref<number>,
  getEl: (i: number) => HTMLElement | undefined,
  opts: RovingOptions = {},
) {
  const {
    scroll = true,
    block = "center",
    inline = "nearest",
    behavior = "smooth",
    focus = true,
  } = opts;

  watch(
    index,
    (newIdx, oldIdx) => {
      if (oldIdx != null) {
        const prev = getEl(oldIdx);
        if (prev) prev.setAttribute("tabindex", "-1");
      }
      const el = getEl(newIdx);
      if (!el) return;
      el.setAttribute("tabindex", "0");
      if (focus) {
        el.focus({ preventScroll: true });
      }
      if (scroll) {
        setTimeout(() => {
          el.scrollIntoView({ block, inline, behavior });
        }, 0);
      }
    },
    { immediate: true },
  );
}
