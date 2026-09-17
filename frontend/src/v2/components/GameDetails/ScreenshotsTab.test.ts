import { shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import ScreenshotsTab from "@/v2/components/GameDetails/ScreenshotsTab.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

describe("ScreenshotsTab overview toggle", () => {
  it("emits the selected overview state", async () => {
    const wrapper = shallowMount(ScreenshotsTab, {
      props: {
        screenshots: [
          {
            id: 4,
            url: "/shot.png",
            isOwn: true,
            isPublic: true,
            isOnOverview: false,
          },
        ],
        overviewTogglable: true,
      },
    });

    await wrapper
      .find('[aria-label="rom.screenshot-add-to-overview"]')
      .trigger("click");

    expect(wrapper.emitted("toggle-overview")).toEqual([[4, true]]);
  });

  it("does not show the control unless the parent enables it", () => {
    const wrapper = shallowMount(ScreenshotsTab, {
      props: {
        screenshots: [{ id: 4, url: "/shot.png", isOnOverview: false }],
      },
    });

    expect(
      wrapper.find('[aria-label="rom.screenshot-add-to-overview"]').exists(),
    ).toBe(false);
  });

  it("disables overview inclusion for private screenshots", () => {
    const wrapper = shallowMount(ScreenshotsTab, {
      props: {
        screenshots: [
          {
            id: 4,
            url: "/shot.png",
            isOwn: true,
            isPublic: false,
            isOnOverview: false,
            overviewDisabled: true,
          },
        ],
        overviewTogglable: true,
      },
    });

    const toggle = wrapper.find(
      '[aria-label="rom.screenshot-overview-requires-public"]',
    );
    expect(toggle.exists()).toBe(true);
    expect(toggle.attributes("disabled")).toBeDefined();
  });
});
