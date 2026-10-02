import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, h, ref } from "vue";
import storePlaying from "@/stores/playing";
import { useGridNav } from "@/v2/composables/useGridNav";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack";
import { useSpatialNav } from "./index";

vi.mock("vue-router", () => ({
  useRoute: () => ({ fullPath: "/rom/1" }),
}));

const padEvents = vi.hoisted(() => new WeakSet<Event>());
vi.mock("@/v2/composables/useGamepad", () => ({
  isPadEvent: (event: Event) => padEvents.has(event),
}));

// Laid out by data attributes since jsdom has no layout engine: a top bar
// link, the game page's action ribbon (a single-row useGridNav) under it,
// and a tab below the ribbon.
const Page = defineComponent({
  setup() {
    const ribbon = ref<HTMLElement | null>(null);
    useGridNav(ribbon, {
      getRows: () => (ribbon.value ? [ribbon.value] : []),
    });
    useSpatialNav().install();
    const btn = (id: string, x: number, y: number) =>
      h("button", { id, "data-x": x, "data-y": y });
    return () =>
      h("div", [
        btn("nav", 0, 0),
        h("div", { ref: ribbon }, [btn("play", 0, 300), btn("fav", 100, 300)]),
        btn("tab", 0, 500),
      ]);
  },
});

describe("useSpatialNav", () => {
  const scrollIntoView = vi.fn();
  let wrapper: ReturnType<typeof mount> | null = null;
  const restores: (() => void)[] = [];

  function stub<K extends keyof HTMLElement>(
    key: K,
    descriptor: PropertyDescriptor,
  ) {
    const original = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      key,
    );
    Object.defineProperty(HTMLElement.prototype, key, {
      configurable: true,
      ...descriptor,
    });
    restores.push(() => {
      if (original) Object.defineProperty(HTMLElement.prototype, key, original);
      else delete (HTMLElement.prototype as Partial<HTMLElement>)[key];
    });
  }

  function el(id: string): HTMLElement {
    return document.getElementById(id)!;
  }

  function press(key: string, { pad = false } = {}): KeyboardEvent {
    const event = new KeyboardEvent("keydown", {
      key,
      bubbles: true,
      cancelable: true,
    });
    if (pad) padEvents.add(event);
    document.activeElement!.dispatchEvent(event);
    return event;
  }

  // A focused text field below the page's tab, between two buttons and above
  // a third.
  const extras: HTMLElement[] = [];
  function field(
    tag: "input" | "textarea",
    value: string,
    caretAt: number,
    type = "text",
  ): HTMLInputElement | HTMLTextAreaElement {
    const place = (node: HTMLElement, x: number, y = 700) => {
      node.dataset.x = String(x);
      node.dataset.y = String(y);
      document.body.append(node);
      extras.push(node);
    };
    for (const [id, x, y] of [
      ["before", 0, 700],
      ["after", 500, 700],
      ["below", 200, 900],
    ] as const) {
      const button = document.createElement("button");
      button.id = id;
      place(button, x, y);
    }
    const input = document.createElement(tag);
    if (input instanceof HTMLInputElement) input.type = type;
    input.value = value;
    place(input, 200);
    input.focus();
    if (caretAt >= 0) input.setSelectionRange(caretAt, caretAt);
    return input;
  }

  beforeEach(() => {
    scrollIntoView.mockClear();
    stub("getBoundingClientRect", {
      value(this: HTMLElement) {
        if (this.dataset.x === undefined) return new DOMRect(0, 0, 0, 0);
        return new DOMRect(
          Number(this.dataset.x),
          Number(this.dataset.y),
          40,
          40,
        );
      },
    });
    stub("scrollIntoView", { value: scrollIntoView });
    wrapper = mount(Page, { attachTo: document.body });
  });

  // A dialog below the page with Cancel and Confirm side by side.
  let dialog: EscapableEntry | null = null;
  let dialogPanel: HTMLElement | null = null;
  function openDialog(withPanel = true): void {
    const panel = document.createElement("div");
    for (const [id, x] of [
      ["cancel", 0],
      ["confirm", 100],
    ] as const) {
      const button = document.createElement("button");
      button.id = id;
      button.dataset.x = String(x);
      button.dataset.y = "600";
      panel.append(button);
    }
    document.body.append(panel);
    dialogPanel = panel;
    dialog = {
      close: () => {},
      persistent: true,
      panel: withPanel ? () => panel : undefined,
    };
    pushEscapable(dialog);
  }

  afterEach(() => {
    extras.splice(0).forEach((node) => node.remove());
    if (dialog) {
      popEscapable(dialog);
      dialog = null;
    }
    dialogPanel?.remove();
    dialogPanel = null;
    wrapper?.unmount();
    wrapper = null;
    restores.splice(0).forEach((restore) => restore());
  });

  it("moves up and down off a single-row grid", () => {
    el("play").focus();

    expect(press("ArrowUp").defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(el("nav"));

    press("ArrowDown");
    expect(document.activeElement).toBe(el("play"));

    press("ArrowDown");
    expect(document.activeElement).toBe(el("tab"));
  });

  it("leaves moves inside the grid to the grid", () => {
    el("play").focus();

    press("ArrowRight");

    expect(document.activeElement).toBe(el("fav"));
  });

  it("does nothing when no control lies in the direction", () => {
    el("nav").focus();

    expect(press("ArrowUp").defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(el("nav"));
  });

  it("scrolls a target outside the viewport into view", () => {
    vi.stubGlobal("innerHeight", 400);
    el("play").focus();

    press("ArrowDown");

    expect(scrollIntoView).toHaveBeenCalledWith(
      expect.objectContaining({ block: "center" }),
    );
    vi.unstubAllGlobals();
  });

  it("skips controls a roving tabindex has taken out of the tab order", () => {
    el("tab").setAttribute("tabindex", "-1");
    el("play").focus();

    expect(press("ArrowDown").defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(el("play"));
  });

  it("leaves the arrows to an open popup's activator", () => {
    el("tab").setAttribute("aria-haspopup", "listbox");
    el("tab").setAttribute("aria-expanded", "true");
    el("tab").focus();

    expect(press("ArrowUp").defaultPrevented).toBe(false);
    expect(document.activeElement).toBe(el("tab"));
  });

  it("stays out of the way while a game is running", () => {
    storePlaying().setPlaying(true);
    el("play").focus();

    press("ArrowUp");

    expect(document.activeElement).toBe(el("play"));
  });

  describe("text fields", () => {
    it("keeps every keyboard arrow in a text field", () => {
      const input = field("input", "abc", 3);

      for (const key of ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"]) {
        expect(press(key).defaultPrevented).toBe(false);
        expect(document.activeElement).toBe(input);
        expect(input.selectionStart).toBe(3);
      }
    });

    it("leaves a single-line field by D-pad up or down from any caret", () => {
      const input = field("input", "abc", 1);

      expect(press("ArrowDown", { pad: true }).defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(el("below"));
      input.focus();
      expect(press("ArrowUp", { pad: true }).defaultPrevented).toBe(true);
      expect(document.activeElement).not.toBe(input);
    });

    it("leaves a textarea by D-pad up or down from any caret", () => {
      const area = field("textarea", "one\ntwo", 5);

      expect(press("ArrowDown", { pad: true }).defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(el("below"));
      area.focus();
      expect(press("ArrowUp", { pad: true }).defaultPrevented).toBe(true);
      expect(document.activeElement).not.toBe(area);
    });

    it("steps the caret by D-pad inside the text", () => {
      const input = field("input", "abc", 1);

      expect(press("ArrowRight", { pad: true }).defaultPrevented).toBe(true);
      expect(input.selectionStart).toBe(2);
      press("ArrowLeft", { pad: true });
      press("ArrowLeft", { pad: true });
      expect(input.selectionStart).toBe(0);
      expect(document.activeElement).toBe(input);
    });

    it("steps over a whole emoji by D-pad", () => {
      const input = field("input", "a🎮b", 1);

      press("ArrowRight", { pad: true });
      expect(input.selectionStart).toBe(3);
      press("ArrowLeft", { pad: true });
      expect(input.selectionStart).toBe(1);
    });

    it("leaves a read-only field by D-pad left or right", () => {
      const input = field("input", "abc", 1);
      input.readOnly = true;

      press("ArrowRight", { pad: true });

      expect(document.activeElement).toBe(el("after"));
    });

    it("steps the caret while a popover outside the field is open", () => {
      const input = field("input", "abc", 1);
      openDialog();

      expect(press("ArrowRight", { pad: true }).defaultPrevented).toBe(true);
      expect(input.selectionStart).toBe(2);
      press("ArrowRight", { pad: true });
      press("ArrowRight", { pad: true });
      expect(document.activeElement).toBe(input);
    });

    it("leaves past the end of the text by D-pad right", () => {
      field("input", "abc", 3);

      press("ArrowRight", { pad: true });

      expect(document.activeElement).toBe(el("after"));
    });

    it("leaves past the start of the text by D-pad left", () => {
      field("input", "abc", 0);

      press("ArrowLeft", { pad: true });

      expect(document.activeElement).toBe(el("before"));
    });

    it("collapses a selection toward the D-pad's side first", () => {
      const input = field("input", "abc", -1);
      input.setSelectionRange(1, 3);

      press("ArrowLeft", { pad: true });
      expect([input.selectionStart, input.selectionEnd]).toEqual([1, 1]);

      input.setSelectionRange(1, 3);
      press("ArrowRight", { pad: true });
      expect([input.selectionStart, input.selectionEnd]).toEqual([3, 3]);
      expect(document.activeElement).toBe(input);
    });

    it("leaves a field without a selection API by D-pad left or right", () => {
      const input = field("input", "", -1, "email");
      vi.spyOn(input, "selectionStart", "get").mockReturnValue(null);

      press("ArrowRight", { pad: true });

      expect(document.activeElement).toBe(el("after"));
    });

    it("keeps the D-pad's up and down in a number field", () => {
      const input = field("input", "4", -1, "number");

      press("ArrowUp", { pad: true });

      expect(document.activeElement).toBe(input);
    });

    it("leaves a field's open popup the D-pad", () => {
      const input = field("input", "abc", 1);
      input.setAttribute("aria-haspopup", "listbox");
      input.setAttribute("aria-expanded", "true");

      expect(press("ArrowDown", { pad: true }).defaultPrevented).toBe(false);
      expect(document.activeElement).toBe(input);
    });
  });

  it("moves between an open dialog's buttons", () => {
    openDialog();
    el("cancel").focus();

    expect(press("ArrowRight").defaultPrevented).toBe(true);
    expect(document.activeElement).toBe(el("confirm"));
  });

  it("keeps focus inside the open dialog", () => {
    openDialog();
    el("cancel").focus();

    press("ArrowUp");

    expect(document.activeElement).toBe(el("cancel"));
  });

  it("moves inside a dialog opened over a running game", () => {
    storePlaying().setPlaying(true);
    openDialog();
    el("cancel").focus();

    press("ArrowRight");

    expect(document.activeElement).toBe(el("confirm"));
  });

  it("leaves an overlay without a panel to its owner", () => {
    openDialog(false);
    el("tab").focus();

    press("ArrowUp");

    expect(document.activeElement).toBe(el("tab"));
  });
});
