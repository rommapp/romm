import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import { useInputModality } from "@/v2/composables/useInputModality";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack";
import RTooltip from "@/v2/lib/structural/RTooltip/RTooltip.vue";
import RSelect from "./RSelect.vue";

describe("RSelect append label", () => {
  const { setModality } = useInputModality();

  afterEach(() => setModality("mouse"));

  function mountWith(options: { info?: string; slot?: string }) {
    return mount(RSelect, {
      props: {
        items: ["autosave"],
        modelValue: "autosave",
        hideDetails: true,
        info: options.info,
      },
      slots: options.slot ? { "append-label": options.slot } : {},
      attachTo: document.body,
    });
  }

  function infoOpen(wrapper: ReturnType<typeof mountWith>) {
    return wrapper.getComponent(RTooltip).props("modelValue");
  }

  it("describes the field with the info outside any aria-hidden subtree", () => {
    const wrapper = mountWith({ info: "Slot info" });
    const field = wrapper.get(".r-select__field");
    const id = field.attributes("aria-describedby");
    const description = document.getElementById(id ?? "");

    expect(description?.textContent).toBe("Slot info");
    expect(description?.closest("[aria-hidden='true']")).toBeNull();
    expect(
      wrapper.get(".r-select__label--append").attributes("aria-hidden"),
    ).toBeUndefined();
    wrapper.unmount();
  });

  it("lets a slot replace the info content", () => {
    const wrapper = mountWith({ info: "Slot info", slot: "MB" });

    expect(wrapper.get(".r-select__label--append").text()).toBe("MB");
    wrapper.unmount();
  });

  it("does not open the menu when the well is clicked", async () => {
    const wrapper = mountWith({ info: "Slot info" });

    await wrapper.get(".r-select__label--append").trigger("click");
    await nextTick();

    expect(wrapper.emitted("open")).toBeUndefined();
    expect(document.querySelector(".r-select__panel")).toBeNull();
    wrapper.unmount();
  });

  it("renders no well without info or slot", () => {
    const wrapper = mountWith({});

    expect(wrapper.find(".r-select__label--append").exists()).toBe(false);
    expect(
      wrapper.get(".r-select__field").attributes("aria-describedby"),
    ).toBeUndefined();
    wrapper.unmount();
  });

  it.each(["key", "pad"] as const)(
    "reveals the info when the field takes %s focus",
    async (modality) => {
      setModality(modality);
      const wrapper = mountWith({ info: "Slot info" });

      await wrapper.get(".r-select__field").trigger("focus");
      expect(infoOpen(wrapper)).toBe(true);

      await wrapper.get(".r-select__field").trigger("blur");
      expect(infoOpen(wrapper)).toBe(false);
      wrapper.unmount();
    },
  );

  it("keeps the info closed on mouse focus", async () => {
    const wrapper = mountWith({ info: "Slot info" });

    await wrapper.get(".r-select__field").trigger("focus");

    expect(infoOpen(wrapper)).toBe(false);
    wrapper.unmount();
  });

  it("closes the info once the menu opens", async () => {
    setModality("key");
    const wrapper = mountWith({ info: "Slot info" });

    await wrapper.get(".r-select__field").trigger("focus");
    await wrapper.get(".r-select__field").trigger("click");

    expect(wrapper.emitted("open")).toHaveLength(1);
    expect(infoOpen(wrapper)).toBe(false);
    wrapper.unmount();
  });
});

describe("RSelect dividerAfter", () => {
  const items = [
    { title: "New", value: "new" },
    { title: "Root", value: "root" },
    { title: "Hack", value: "hack" },
  ];

  async function openMenu(dividerAfter: (item: { value: string }) => boolean) {
    const wrapper = mount(RSelect, {
      props: {
        items,
        modelValue: "root",
        dividerAfter: dividerAfter as (item: unknown) => boolean,
      },
      attachTo: document.body,
    });
    await wrapper.get(".r-select__field").trigger("click");
    await nextTick();
    return wrapper;
  }

  function menuRows() {
    return Array.from(document.querySelectorAll(".r-select__list > li")).map(
      (li) =>
        li.classList.contains("r-select__divider") ? "---" : li.textContent,
    );
  }

  it("draws a divider below the matched item without shifting indexes", async () => {
    const wrapper = await openMenu((item) => item.value === "new");

    expect(menuRows()).toEqual(["New", "---", "Root", "Hack"]);
    const indexes = Array.from(
      document.querySelectorAll("[data-r-select-index]"),
    ).map((li) => li.getAttribute("data-r-select-index"));
    expect(indexes).toEqual(["0", "1", "2"]);
    wrapper.unmount();
  });

  it("never leaves a divider trailing the last row", async () => {
    const wrapper = await openMenu((item) => item.value === "hack");

    expect(menuRows()).toEqual(["New", "Root", "Hack"]);
    wrapper.unmount();
  });
});

describe("RSelect itemSearchTerms", () => {
  const items = [
    { title: "PlayStation 2", value: "ps2" },
    { title: "Nintendo 64", value: "n64" },
  ];

  async function searchFor(
    search: string,
    itemSearchTerms?: (item: { value: string }) => string[],
  ) {
    const wrapper = mount(RSelect, {
      props: {
        items,
        modelValue: null,
        searchable: true,
        search,
        itemSearchTerms: itemSearchTerms as
          ((item: unknown) => string[]) | undefined,
      },
      attachTo: document.body,
    });
    await wrapper.get(".r-select__field").trigger("click");
    await nextTick();
    const rows = Array.from(
      document.querySelectorAll("[data-r-select-index]"),
    ).map((li) => li.textContent?.trim());
    wrapper.unmount();
    return rows;
  }

  it("matches only the title without extra terms", async () => {
    expect(await searchFor("PS2")).toEqual([]);
  });

  it("matches an extra term case-insensitively", async () => {
    expect(await searchFor("PS2", (item) => [item.value])).toEqual([
      "PlayStation 2",
    ]);
  });

  it("still matches the title alongside extra terms", async () => {
    expect(await searchFor("nintendo", (item) => [item.value])).toEqual([
      "Nintendo 64",
    ]);
  });
});

// Regression guard: `.r-select__value` is a flex row with a 6px gap (it
// spaces chips apart). A multi-select without chips renders its titles and
// the "," separator as plain spans, so hoisting them into that row put the
// gap on both sides of the comma and the activator read "A , B".
describe("RSelect multi-select without chips", () => {
  const items = [
    { title: "Screenshot", value: "screenshot" },
    { title: "Manual", value: "manual" },
  ];

  it("keeps the titles and separator in one box inside the value row", () => {
    const wrapper = mount(RSelect, {
      props: { items, multiple: true, modelValue: ["screenshot", "manual"] },
    });

    const value = wrapper.get(".r-select__value");
    expect(value.element.children).toHaveLength(1);

    const selection = wrapper.get(".r-select__selection");
    expect(selection.findAll(".r-select__title").map((n) => n.text())).toEqual([
      "Screenshot",
      "Manual",
    ]);
    expect(selection.findAll(".r-select__sep")).toHaveLength(1);
    expect(selection.text()).toBe("Screenshot, Manual");
  });
});

describe("RSelect rules", () => {
  it("re-checks a touched field when its rules change", async () => {
    const wrapper = mount(RSelect, {
      props: { items: ["a", "b"], modelValue: "a", rules: [] },
    });
    wrapper.vm.validate();
    await nextTick();
    expect(wrapper.find(".r-select__details--error").exists()).toBe(false);

    await wrapper.setProps({ rules: [() => "Pick another"] });
    expect(wrapper.get(".r-select__details--error").text()).toBe(
      "Pick another",
    );
    wrapper.unmount();
  });
});

describe("RSelect inside an overlay", () => {
  const dialog: EscapableEntry = {
    close: vi.fn(),
    persistent: false,
  };

  afterEach(() => {
    popEscapable(dialog);
  });

  it("closes only its own menu on Escape, leaving the dialog open", async () => {
    pushEscapable(dialog);
    const wrapper = mount(RSelect, {
      props: { items: ["a", "b"], modelValue: "a", hideDetails: true },
      attachTo: document.body,
    });

    await wrapper.get(".r-select__field").trigger("keydown", { key: "Enter" });
    expect(document.querySelector(".r-select__panel")).not.toBeNull();

    wrapper
      .get(".r-select__field")
      .element.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
    await nextTick();

    expect(document.querySelector(".r-select__panel")).toBeNull();
    expect(dialog.close).not.toHaveBeenCalled();

    wrapper
      .get(".r-select__field")
      .element.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
    expect(dialog.close).toHaveBeenCalledOnce();
    wrapper.unmount();
  });

  it("stays open for a press inside an overlay opened above it", async () => {
    const wrapper = mount(RSelect, {
      props: { items: ["a", "b"], modelValue: "a", hideDetails: true },
      attachTo: document.body,
    });
    await wrapper.get(".r-select__field").trigger("keydown", { key: "Enter" });
    expect(document.querySelector(".r-select__panel")).not.toBeNull();

    const nested = document.createElement("div");
    document.body.append(nested);
    const menu: EscapableEntry = {
      close: vi.fn(),
      persistent: false,
      panel: () => nested,
    };
    pushEscapable(menu);

    nested.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }));
    await nextTick();
    expect(document.querySelector(".r-select__panel")).not.toBeNull();

    popEscapable(menu);
    nested.remove();
    document.body.dispatchEvent(
      new PointerEvent("pointerdown", { bubbles: true }),
    );
    await nextTick();
    expect(document.querySelector(".r-select__panel")).toBeNull();
    wrapper.unmount();
  });
});

describe("RSelect null-valued item", () => {
  const items = [
    { title: "No limit", value: null },
    { title: "12", value: 12 },
  ];

  it("shows and checks an item whose value is null", async () => {
    const wrapper = mount(RSelect, {
      props: { items, modelValue: null, clearable: true },
      attachTo: document.body,
    });

    expect(wrapper.get(".r-select__value").text()).toBe("No limit");
    expect(wrapper.find(".r-select__clear").exists()).toBe(false);
    await wrapper.get(".r-select__field").trigger("click");
    await nextTick();
    const selected = document.querySelector(
      ".r-select__list [aria-selected='true']",
    );
    expect(selected?.textContent).toContain("No limit");
    wrapper.unmount();
  });

  it("shows nothing for an undefined model", () => {
    const wrapper = mount(RSelect, { props: { items, modelValue: undefined } });

    expect(wrapper.get(".r-select__value").text()).not.toContain("No limit");
  });
});

describe("RSelect stacked label", () => {
  it("names the field after its label, then its value", () => {
    const wrapper = mount(RSelect, {
      props: {
        items: ["Kids", "Adults"],
        modelValue: "Kids",
        label: "Permission group",
        prefixLabel: "stacked",
      },
    });
    const field = wrapper.get(".r-select__field");
    const [labelId, fieldId] = (
      field.attributes("aria-labelledby") ?? ""
    ).split(" ");

    expect(wrapper.get(`#${labelId}`).text()).toBe("Permission group");
    expect(fieldId).toBe(field.attributes("id"));
  });
});
