import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import i18n, { loadLocale } from "@/locales";
import LogViewer from "./LogViewer.vue";

const { copy } = vi.hoisted(() => ({ copy: vi.fn() }));

vi.mock("@/services/api", () => ({
  default: {
    get: vi.fn(async () => ({
      data: [
        { ts: 0, level: "INFO", module: "scan", message: "first" },
        { ts: 1000, level: "ERROR", module: "rq", message: "second" },
      ],
    })),
  },
}));
vi.mock("@/v2/composables/useSocketEvent", () => ({
  useSocketEvent: vi.fn(),
}));
vi.mock("@/v2/composables/useClipboard", () => ({
  useClipboard: () => ({ isSupported: true, copy }),
}));

// happy-dom lays nothing out, so a windowed list would render no rows.
const WholeList = defineComponent({
  props: { items: { type: Array, default: () => [] } },
  template: `<div><slot name="prepend" /><div v-for="(item, index) in items" :key="index"><slot :item="item" :index="index" /></div></div>`,
});

async function render() {
  const wrapper = mount(LogViewer, {
    global: { plugins: [i18n], stubs: { RVirtualScroller: WholeList } },
  });
  await flushPromises();
  return wrapper;
}

beforeAll(async () => {
  await loadLocale("en_US");
});

beforeEach(() => {
  setActivePinia(createPinia());
  copy.mockReset();
  copy.mockResolvedValue(true);
});

describe("LogViewer", () => {
  it("copies every shown line, oldest first, through the clipboard composable", async () => {
    const wrapper = await render();

    await wrapper.find('[aria-label="Copy to clipboard"]').trigger("click");

    expect(copy).toHaveBeenCalledTimes(1);
    const [text, opts] = copy.mock.calls[0];
    expect(text.split("\n")).toEqual([
      "[1970-01-01T00:00:00.000Z] INFO [scan] first",
      "[1970-01-01T00:00:01.000Z] ERROR [rq] second",
    ]);
    expect(opts).toEqual({ successMessage: "Logs copied to clipboard" });
  });

  it("copies a single line when its row is clicked", async () => {
    const wrapper = await render();

    await wrapper.find(".r-v2-logs__row").trigger("click");

    expect(copy).toHaveBeenCalledWith(
      "[1970-01-01T00:00:01.000Z] ERROR [rq] second",
      { successMessage: "Line copied to clipboard" },
    );
  });
});
