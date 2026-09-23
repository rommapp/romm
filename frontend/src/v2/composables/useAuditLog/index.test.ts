import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AuditEventSchema } from "@/__generated__";
import auditApi from "@/services/api/audit";
import { useAuditLog } from "@/v2/composables/useAuditLog";

vi.mock("@/services/api/audit", () => ({
  default: { getAuditEvents: vi.fn() },
}));

const getAuditEvents = vi.mocked(auditApi.getAuditEvents);

function page(ids: number[], total: number) {
  return {
    data: {
      items: ids.map((id) => ({ id }) as AuditEventSchema),
      total,
      limit: 2,
      offset: 0,
    },
  } as Awaited<ReturnType<typeof auditApi.getAuditEvents>>;
}

beforeEach(() => {
  getAuditEvents.mockReset();
});

describe("useAuditLog", () => {
  it("pins later pages to the newest event of the first", async () => {
    getAuditEvents
      .mockResolvedValueOnce(page([9, 8], 3))
      .mockResolvedValueOnce(page([7], 3));
    const log = useAuditLog(2);

    await log.reset({ categories: ["consumption"] });
    await log.loadMore();

    expect(getAuditEvents).toHaveBeenLastCalledWith({
      categories: ["consumption"],
      maxId: 9,
      limit: 2,
      offset: 2,
    });
    expect(log.events.value.map((e) => e.id)).toEqual([9, 8, 7]);
    expect(log.hasMore.value).toBe(false);
  });

  it("drops a page that a newer reset overtook", async () => {
    let resolveFirst: (value: ReturnType<typeof page>) => void = () => {};
    getAuditEvents
      .mockReturnValueOnce(new Promise((resolve) => (resolveFirst = resolve)))
      .mockResolvedValueOnce(page([5], 1));
    const log = useAuditLog(2);

    const stale = log.reset({ search: "old" });
    await log.reset({ search: "new" });
    resolveFirst(page([1, 2], 2));
    await stale;

    expect(log.events.value.map((e) => e.id)).toEqual([5]);
    expect(log.loading.value).toBe(false);
  });
});
