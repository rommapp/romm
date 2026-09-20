import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import LocationChip from "./LocationChip.vue";

const { copy } = vi.hoisted(() => ({ copy: vi.fn() }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useClipboard", () => ({
  useClipboard: () => ({ isSupported: true, copy }),
}));

const PATH = "roms/nes/Hacks/Zelda (USA) [T-Eng].nes";

function mountChip(path = PATH) {
  return mount(LocationChip, { props: { path } });
}

beforeEach(() => {
  copy.mockReset();
  copy.mockResolvedValue(true);
});

describe("LocationChip", () => {
  it("shows the path in full, unabbreviated", () => {
    const wrapper = mountChip();

    expect(wrapper.text()).toContain(PATH);
  });

  it("keeps the path in the title and label so it is reachable on hover and by a screen reader", () => {
    const button = mountChip().find("button");

    expect(button.attributes("title")).toContain(PATH);
    expect(button.attributes("aria-label")).toContain(PATH);
  });

  // Going through the composable is what applies the secure-context guard:
  // over plain HTTP `navigator.clipboard` is undefined and a direct call throws.
  it("copies through the clipboard composable", async () => {
    const wrapper = mountChip();

    await wrapper.find("button").trigger("click");
    await flushPromises();

    expect(copy).toHaveBeenCalledWith(PATH, {
      successMessage: "rom.location-copied",
    });
  });
});
