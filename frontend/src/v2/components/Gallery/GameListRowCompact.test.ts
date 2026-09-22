import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import GameListRow from "./GameListRow.vue";
import { rom } from "./listRowFixture";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: "en" } }),
}));

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRouter: () => ({ push: vi.fn() }),
}));

const smAndDown = ref(true);
vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown }),
}));

function mountRow(props: Record<string, unknown> = {}) {
  return mount(GameListRow, {
    props: { rom: rom(), ...props },
    global: {
      stubs: {
        GameActionBtn: true,
        GameCard: true,
        RCheckbox: true,
        RChip: true,
        RIcon: true,
        RPlatformIcon: true,
        RTooltip: true,
        SiblingBadge: true,
      },
    },
  });
}

describe("list row on phones and tablets", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    smAndDown.value = true;
  });

  it("trades the columns for a title and a facts line", () => {
    const wrapper = mountRow();

    expect(wrapper.find(".game-list-row__compact").exists()).toBe(true);
    expect(wrapper.find(".game-list-row__cell").exists()).toBe(false);
    expect(wrapper.find(".game-list-row__facts").text()).toBe(
      "Super Nintendo  ·  4 MB  ·  1995",
    );
  });

  it("leaves the platform out where the whole list shares one", () => {
    const wrapper = mountRow({ showPlatformColumn: false });

    expect(wrapper.find(".game-list-row__facts").text()).toBe("4 MB  ·  1995");
  });

  // An empty file is still a size worth reading, not a missing one.
  it("states a zero-byte file's size", () => {
    const wrapper = mountRow({ rom: rom({ fs_size_bytes: 0 }) });

    expect(wrapper.find(".game-list-row__facts").text()).toContain("0 Bytes");
  });

  it("keeps the columns on wider viewports", () => {
    smAndDown.value = false;

    const wrapper = mountRow();

    expect(wrapper.find(".game-list-row__compact").exists()).toBe(false);
    expect(wrapper.find(".game-list-row__cell").exists()).toBe(true);
  });

  it("asks the parent to open its detail panel", async () => {
    const wrapper = mountRow({ expandable: true });

    await wrapper.get(".game-list-row__chevron").trigger("click");

    expect(wrapper.emitted("toggle-expand")).toHaveLength(1);
  });

  it("offers no chevron where the row cannot grow", () => {
    const wrapper = mountRow();

    expect(wrapper.find(".game-list-row__chevron").exists()).toBe(false);
  });

  it("moves the remaining columns into the open panel", () => {
    const wrapper = mountRow({ expandable: true, expanded: true });

    const fields = wrapper
      .findAll(".game-list-row__field-value")
      .map((el) => el.text());
    // The file name, plus what the facts line leaves out.
    expect(fields).toContain("Chrono Trigger.sfc");
    expect(fields).toContain("9.1");
    expect(fields).toContain("USA");
    expect(fields).toContain("en");
  });
});
