import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, reactive } from "vue";
import type { AuditEventSchema } from "@/__generated__";
import i18n, { loadLocale } from "@/locales";
import auditApi from "@/services/api/audit";
import { makeAuditEvent } from "@/v2/utils/auditEvents.fixtures";
import EventLog from "./EventLog.vue";

const route = reactive<{ query: Record<string, string> }>({ query: {} });

vi.mock("vue-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("vue-router")>()),
  useRoute: () => route,
  useRouter: () => ({ replace: vi.fn(), currentRoute: { value: route } }),
}));
vi.mock("@/services/api/audit", () => ({
  default: { getAuditEvents: vi.fn() },
}));
vi.mock("@/services/api/user", () => ({
  default: { fetchUsers: vi.fn(async () => ({ data: [] })) },
}));

const getAuditEvents = vi.mocked(auditApi.getAuditEvents);

function event(
  id: number,
  action: string,
  data: AuditEventSchema["data"],
): AuditEventSchema {
  return makeAuditEvent({
    id,
    action,
    actor_name: "maria",
    target_id: "33",
    target_name: "Hollow Knight",
    ip_address: "192.168.1.20",
    device_name: "Steam Deck",
    data,
  });
}

const EVENTS = [
  event(3, "rom.play", { duration_ms: 7_633_360 }),
  event(2, "rom.download", { file_name: "hk.zip", size_bytes: 1024 }),
  event(1, "rom.teleport", {}),
];

// happy-dom lays nothing out, so a windowed list would render no rows.
const WholeList = defineComponent({
  props: { items: { type: Array, default: () => [] } },
  template: `<div><slot name="prepend" /><div v-for="(item, index) in items" :key="index"><slot :item="item" :index="index" /></div></div>`,
});

function render() {
  return mount(EventLog, {
    global: {
      plugins: [i18n],
      stubs: {
        RouterLink: { template: "<a><slot /></a>" },
        RVirtualScroller: WholeList,
      },
    },
  });
}

beforeAll(async () => {
  await loadLocale("en_US");
});

beforeEach(() => {
  setActivePinia(createPinia());
  route.query = {};
  getAuditEvents.mockReset();
  getAuditEvents.mockResolvedValue({
    data: { items: EVENTS, total: 3, limit: 50, offset: 0 },
  } as Awaited<ReturnType<typeof auditApi.getAuditEvents>>);
});

describe("EventLog", () => {
  it("lists every event, a long play and an unknown action included", async () => {
    const wrapper = render();
    await flushPromises();

    const text = wrapper.text();
    expect(text).toContain("Played Hollow Knight");
    expect(text).toContain("Downloaded Hollow Knight");
    expect(text).toContain("rom.teleport Hollow Knight");
    expect(text).toContain("Steam Deck");
  });

  it("searches once typing pauses, or straight away on Enter", async () => {
    // lodash's debounce reads the clock; setImmediate stays real for flushPromises.
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
    try {
      const wrapper = render();
      await flushPromises();
      getAuditEvents.mockClear();
      const input = wrapper.find('input[placeholder="Search events"]');

      await input.setValue("192");
      await input.setValue("192.168");
      await flushPromises();
      expect(getAuditEvents).not.toHaveBeenCalled();

      vi.advanceTimersByTime(300);
      await flushPromises();
      expect(getAuditEvents).toHaveBeenCalledOnce();
      expect(getAuditEvents).toHaveBeenCalledWith(
        expect.objectContaining({ search: "192.168" }),
      );

      getAuditEvents.mockClear();
      await input.setValue("steam");
      await input.trigger("keyup", { key: "Enter" });
      await flushPromises();
      expect(getAuditEvents).toHaveBeenCalledWith(
        expect.objectContaining({ search: "steam" }),
      );
    } finally {
      vi.useRealTimers();
    }
  });
});
