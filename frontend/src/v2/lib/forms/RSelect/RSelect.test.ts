import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import { nextTick } from "vue";
import { useInputModality } from "@/v2/composables/useInputModality";
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
      props: { items, modelValue: "root", dividerAfter },
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
