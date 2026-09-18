import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import RChip from "../primitives/RChip/RChip.vue";
import {
  ChromeLabelsKey,
  DEFAULT_CHROME_LABELS,
  useChromeLabels,
  type ChromeLabels,
} from "./chromeLabels";

const Consumer = {
  setup() {
    return { labels: useChromeLabels() };
  },
  template: `<i>{{ labels.close }}</i>`,
};

function bundle(overrides: Partial<ChromeLabels> = {}): ChromeLabels {
  return { ...DEFAULT_CHROME_LABELS, ...overrides };
}

describe("useChromeLabels", () => {
  it("falls back to English when nothing is provided", () => {
    const wrapper = mount(Consumer);
    expect(wrapper.text()).toBe("Close");
    wrapper.unmount();
  });

  it("reads the injected bundle", () => {
    const wrapper = mount(Consumer, {
      global: { provide: { [ChromeLabelsKey as symbol]: bundle({ close: "Schließen" }) } },
    });
    expect(wrapper.text()).toBe("Schließen");
    wrapper.unmount();
  });

  it("re-reads a getter-backed bundle, so a locale switch propagates", async () => {
    let locale = "en_US";
    const reactiveBundle: ChromeLabels = {
      ...DEFAULT_CHROME_LABELS,
      get close() {
        return locale === "de_DE" ? "Schließen" : "Close";
      },
    };
    const wrapper = mount(Consumer, {
      global: { provide: { [ChromeLabelsKey as symbol]: reactiveBundle } },
    });
    expect(wrapper.text()).toBe("Close");

    locale = "de_DE";
    await wrapper.vm.$forceUpdate();
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toBe("Schließen");
    wrapper.unmount();
  });
});

// The label props that predate the injected bundle defaulted to English
// literals and were never passed by any call site, so they rendered English
// in every locale. These assertions are what stops that regressing.
describe("primitives consume the injected bundle", () => {
  it("RChip's remove button uses the injected label", () => {
    const wrapper = mount(RChip, {
      props: { closable: true },
      global: { provide: { [ChromeLabelsKey as symbol]: bundle({ remove: "Entfernen" }) } },
    });
    expect(wrapper.get("button.r-chip__close").attributes("aria-label")).toBe(
      "Entfernen",
    );
    wrapper.unmount();
  });

  it("RChip falls back to English with no provider", () => {
    const wrapper = mount(RChip, { props: { closable: true } });
    expect(wrapper.get("button.r-chip__close").attributes("aria-label")).toBe(
      "Remove",
    );
    wrapper.unmount();
  });
});
