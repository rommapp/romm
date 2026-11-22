import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { SetupExistingPlatform } from "@/__generated__";
import { RCheckbox } from "@/lib";
import { platformFixture } from "@/utils/platform.fixtures";
import SetupStepPlatforms from "./SetupStepPlatforms.vue";

vi.mock("vue-i18n");

const supported = [
  platformFixture({ slug: "ngc", name: "Nintendo GameCube" }),
  platformFixture({ slug: "genesis", name: "Sega Genesis" }),
  platformFixture({ slug: "n64", name: "Nintendo 64" }),
];

function mountStep(
  existing: SetupExistingPlatform[],
  supportedPlatforms = supported,
) {
  return mount(SetupStepPlatforms, {
    props: {
      libraryInfo: {
        library_ready: true,
        library_structure: "{platform}/roms",
        existing_platforms: existing,
        supported_platforms: supportedPlatforms,
      },
      selectedNewPlatforms: [],
    },
    global: {
      stubs: {
        PlatformIcon: true,
        RChip: { template: "<span class='chip'><slot /></span>" },
        RCollapsible: true,
        REmptyState: true,
        RIcon: true,
        RSegmentedControl: true,
        RTag: true,
        RTextField: true,
      },
    },
  });
}

function detectedRows(wrapper: ReturnType<typeof mountStep>) {
  return wrapper.findAll("[data-state='detected']").map((row) => ({
    name: row.get(".r-setup-platforms__item-name").text(),
    folder: row.get(".r-setup-platforms__item-slug").text(),
    roms: row.get(".r-setup-platforms__item-state .chip").text(),
  }));
}

async function selectAll(wrapper: ReturnType<typeof mountStep>) {
  await wrapper.getComponent(RCheckbox).vm.$emit("update:modelValue", true);
  return wrapper.emitted("update:selectedNewPlatforms")?.[0]?.[0];
}

describe("SetupStepPlatforms detected folders", () => {
  it("identifies alias folders by their resolved slug, one row per folder", () => {
    const wrapper = mountStep([
      { fs_slug: "gamecube", slug: "ngc", rom_count: 2 },
      { fs_slug: "megadrive", slug: "genesis", rom_count: 3 },
      { fs_slug: "genesis", slug: "genesis", rom_count: 1 },
      { fs_slug: "mystery", slug: "mystery", rom_count: 4 },
    ]);

    expect(detectedRows(wrapper)).toEqual([
      { name: "mystery", folder: "mystery", roms: "4" },
      { name: "Nintendo GameCube", folder: "gamecube", roms: "2" },
      { name: "Sega Genesis", folder: "megadrive", roms: "3" },
      { name: "Sega Genesis", folder: "genesis", roms: "1" },
    ]);
  });

  it("only offers platforms that no folder resolves to", async () => {
    const wrapper = mountStep([
      { fs_slug: "gamecube", slug: "ngc", rom_count: 2 },
    ]);

    expect(await selectAll(wrapper)).toEqual(["genesis", "n64"]);
  });

  it("matches a platform row whose fs_slug is the alias folder", async () => {
    const wrapper = mountStep(
      [{ fs_slug: "gamecube", slug: "ngc", rom_count: 0 }],
      [
        platformFixture({
          slug: "ngc",
          fs_slug: "gamecube",
          name: "Nintendo GameCube",
        }),
        platformFixture({ slug: "n64", name: "Nintendo 64" }),
      ],
    );

    expect(detectedRows(wrapper)).toEqual([
      { name: "Nintendo GameCube", folder: "gamecube", roms: "0" },
    ]);
    expect(await selectAll(wrapper)).toEqual(["n64"]);
  });
});
