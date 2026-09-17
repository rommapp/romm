import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import { nextTick } from "vue";
import RSelect from "./RSelect.vue";

describe("RSelect append label", () => {
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

  it("reads the info as the field's description, not its name", () => {
    const wrapper = mountWith({ info: "Slot info" });
    const well = wrapper.get(".r-select__label--append");

    expect(well.attributes("aria-hidden")).toBe("true");
    expect(well.text()).toBe("Slot info");
    expect(wrapper.get(".r-select__field").attributes("aria-describedby")).toBe(
      well.attributes("id"),
    );
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
