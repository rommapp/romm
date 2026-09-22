import { RAlert, RChip, RSteps } from "@v2/lib";
import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
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
      global: {
        provide: {
          [ChromeLabelsKey as symbol]: bundle({ close: "Schließen" }),
        },
      },
    });
    expect(wrapper.text()).toBe("Schließen");
    wrapper.unmount();
  });
});

describe("primitives consume the injected bundle", () => {
  it("RChip's remove button uses the injected label", () => {
    const wrapper = mount(RChip, {
      props: { closable: true },
      global: {
        provide: {
          [ChromeLabelsKey as symbol]: bundle({ remove: "Entfernen" }),
        },
      },
    });
    expect(wrapper.get("button.r-chip__close").attributes("aria-label")).toBe(
      "Entfernen",
    );
    wrapper.unmount();
  });

  it("RAlert's close button uses the injected label", () => {
    const wrapper = mount(RAlert, {
      props: { closable: true },
      global: {
        provide: {
          [ChromeLabelsKey as symbol]: bundle({ close: "Schließen" }),
        },
      },
    });
    expect(wrapper.get("button.r-alert__close").attributes("aria-label")).toBe(
      "Schließen",
    );
    wrapper.unmount();
  });

  it("RSteps builds its stepper name from the injected formatter", () => {
    const wrapper = mount(RSteps, {
      props: { total: 3, current: 2 },
      global: {
        provide: {
          [ChromeLabelsKey as symbol]: bundle({
            step: (current, total) => `Schritt ${current} von ${total}`,
          }),
        },
      },
    });
    expect(wrapper.get("ol.r-steps").attributes("aria-label")).toBe(
      "Schritt 2 von 3",
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
