import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { ScanningPlatform } from "@/stores/scanning";
import ScanPlatform from "./ScanPlatform.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function mountPlatform(overrides: Partial<ScanningPlatform> = {}) {
  const platform: ScanningPlatform = {
    id: 1,
    name: "Game Boy Color",
    display_name: "Game Boy Color",
    slug: "gbc",
    fs_slug: "gbc",
    is_identified: true,
    roms: [],
    new_firmware_count: 0,
    ...overrides,
  };

  return mount(ScanPlatform, {
    props: { platform, open: true },
    global: {
      stubs: {
        RCollapsible: {
          template: "<div><slot /><slot name='header-append' /></div>",
        },
        RPlatformIcon: true,
        RTag: {
          props: ["text"],
          template: "<span class='r-tag'>{{ text }}</span>",
        },
        RVirtualScroller: true,
      },
    },
  });
}

describe("ScanPlatform", () => {
  // Firmware already in the library is not a scan result: the header used to
  // show the platform's total firmware count, so every re-scan looked like it
  // had discovered firmware (issue #4049).
  it("hides the firmware tag when the scan found no new firmware", () => {
    const wrapper = mountPlatform({ new_firmware_count: 0 });

    expect(wrapper.findAll(".r-tag")).toHaveLength(1);
  });

  it("shows the count of firmware discovered by this scan", () => {
    const wrapper = mountPlatform({ new_firmware_count: 2 });

    const tags = wrapper.findAll(".r-tag");
    expect(tags).toHaveLength(2);
    expect(tags[1].text()).toBe("2");
  });

  // The body only lists ROMs, so a firmware-only platform rendered an empty
  // panel instead of the "no new roms" message.
  it("reports no new roms even when firmware was found", () => {
    const wrapper = mountPlatform({ new_firmware_count: 2 });

    expect(wrapper.text()).toContain("scan.no-new-roms");
  });
});
