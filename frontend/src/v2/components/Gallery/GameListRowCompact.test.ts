import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import storeGalleryRoms from "@/v2/stores/galleryRoms";
import storeGallerySelection from "@/v2/stores/gallerySelection";
import GameListRow from "./GameListRow.vue";
import { rom } from "./listRowFixture";

vi.mock("vue-i18n");

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
        PlatformIcon: true,
        RTooltip: true,
        SiblingBadge: true,
      },
    },
  });
}

/** The facts line's text pieces, separators included. */
function facts(wrapper: ReturnType<typeof mountRow>): string[] {
  return wrapper
    .findAll(".r-list-compact__facts > span")
    .map((el) => el.text());
}

describe("list row on phones and tablets", () => {
  beforeEach(() => {
    smAndDown.value = true;
  });

  it("trades the columns for a title and a facts line", () => {
    const wrapper = mountRow();

    expect(wrapper.find(".game-list-row__compact").exists()).toBe(true);
    expect(wrapper.find(".game-list-row__cell").exists()).toBe(false);
    expect(facts(wrapper)).toEqual(["Super Nintendo", "·", "1995"]);
  });

  it("leaves the platform out where the whole list shares one", () => {
    const wrapper = mountRow({ showPlatformColumn: false });

    expect(facts(wrapper)).toEqual(["1995"]);
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
    expect(fields).toContain("4 MB");
    expect(fields).toContain("9.1");
    expect(fields).toContain("USA");
    expect(fields).toContain("en");
  });
});

describe("list row selection", () => {
  beforeEach(() => {
    smAndDown.value = false;
  });

  // Seeded after mounting: the first gallery row to mount resets the store.
  async function mountGalleryRow(attrs: Record<string, unknown> = {}) {
    const wrapper = mountRow({ rom: undefined, position: 0, ...attrs });
    storeGalleryRoms().byPosition.set(0, rom());
    await flushPromises();
    return wrapper;
  }

  it("selects on Space from its name link", async () => {
    const wrapper = await mountGalleryRow();

    await wrapper.get("a.game-list-row__name").trigger("keydown", { key: " " });

    expect(storeGallerySelection().ids).toEqual([rom().id]);
    expect(wrapper.get("[role=row]").attributes("aria-selected")).toBe("true");
  });

  it("is a row with one cell on phones", async () => {
    smAndDown.value = true;
    const row = (await mountGalleryRow()).get("[role=row]");

    expect(
      Array.from(row.element.children).map((c) => c.getAttribute("role")),
    ).toEqual(["gridcell"]);
  });
  it("is a grid row of cells, with the name as its link", async () => {
    const wrapper = await mountGalleryRow({ "aria-rowindex": 4 });
    const row = wrapper.get("[role=row]");

    expect(row.attributes("aria-rowindex")).toBe("4");
    expect(row.attributes("aria-selected")).toBe("false");
    expect(
      row.element.children.length,
      "every column is a cell",
    ).toBeGreaterThan(1);
    for (const child of Array.from(row.element.children)) {
      expect(child.getAttribute("role")).toBe("gridcell");
    }
    expect(row.get("a.game-list-row__name").attributes("href")).toBe(
      `/rom/${rom().id}`,
    );
  });
});
