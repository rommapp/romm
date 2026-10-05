import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { HashMatcher } from "@/v2/composables/useScanProviders";
import ScanHashMatcherSwitches from "./ScanHashMatcherSwitches.vue";

vi.mock("vue-i18n");

const HASHEOUS: HashMatcher = {
  value: "hasheous",
  name: "Hasheous",
  logo: "/assets/scrappers/hasheous.png",
  blockedReason: null,
  switchEnabled: true,
};
const PLAYMATCH: HashMatcher = {
  value: "playmatch",
  name: "Playmatch",
  logo: "/assets/scrappers/playmatch.png",
  blockedReason: "Requires IGDB",
  switchEnabled: false,
};

// Renders the activator and exposes the tooltip text for assertions.
const RTooltip = {
  props: {
    text: { type: String, default: "" },
    openOnTap: { type: Boolean, default: false },
  },
  template: `<div class="tip" :data-text="text" :data-tap="openOnTap"><slot name="activator" :props="{}" /></div>`,
};

function mountSwitches(on: string[] = []) {
  return mount(ScanHashMatcherSwitches, {
    props: {
      matchers: [HASHEOUS, PLAYMATCH],
      isOn: (m: HashMatcher) => on.includes(m.value),
    },
    global: { stubs: { RTooltip, RAvatar: true } },
  });
}

describe("ScanHashMatcherSwitches", () => {
  it("renders a labelled switch per matcher showing its state", () => {
    const switches = mountSwitches(["hasheous"]).findAll('[role="switch"]');

    expect(switches.map((s) => s.attributes("aria-label"))).toEqual([
      "Hasheous",
      "Playmatch",
    ]);
    expect(switches[0]!.attributes("aria-checked")).toBe("true");
    expect(switches[1]!.attributes("aria-checked")).toBe("false");
  });

  it("emits the matcher and its next state when toggled", async () => {
    const wrapper = mountSwitches();

    await wrapper.get('[aria-label="Hasheous"]').trigger("click");

    expect(wrapper.emitted("toggle")).toEqual([["hasheous", true]]);
  });

  it("disables a blocked matcher and explains why in its tooltip", () => {
    const wrapper = mountSwitches();
    const tips = wrapper.findAll(".tip");

    expect(
      wrapper.get('[aria-label="Playmatch"]').attributes("disabled"),
    ).toBeDefined();
    expect(tips[0]!.attributes("data-text")).toBe("Hasheous");
    expect(tips[1]!.attributes("data-text")).toBe("Playmatch: Requires IGDB");
  });

  it("lets keyboard and touch users reach a blocked matcher's reason", () => {
    const wrapper = mountSwitches();
    const [open, blocked] = wrapper.findAll(".r-v2-hash-matchers__matcher");
    const tips = wrapper.findAll(".tip");

    expect(open!.attributes("tabindex")).toBeUndefined();
    expect(blocked!.attributes("tabindex")).toBe("0");
    expect(blocked!.attributes("role")).toBe("group");
    expect(blocked!.attributes("aria-label")).toBe("Playmatch: Requires IGDB");
    expect(tips[0]!.attributes("data-tap")).toBe("false");
    expect(tips[1]!.attributes("data-tap")).toBe("true");
  });
});
