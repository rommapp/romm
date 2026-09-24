import { computed, ref, shallowRef } from "vue";
import type { AuditEventSchema } from "@/__generated__";
import auditApi, { type AuditEventsQuery } from "@/services/api/audit";

export type AuditLogFilters = Omit<
  AuditEventsQuery,
  "maxId" | "limit" | "offset"
>;

/** Pages through the audit log, newest first, pinned to what the first page saw. */
export function useAuditLog(pageSize = 50) {
  const events = shallowRef<AuditEventSchema[]>([]);
  const total = ref(0);
  const loading = ref(false);
  const loadingMore = ref(false);

  let filters: AuditLogFilters = {};
  // Events recorded after the first page would shift every later offset.
  let maxId: number | undefined;
  // A reset while a page is in flight makes that page stale.
  let generation = 0;

  const hasMore = computed(() => events.value.length < total.value);

  async function reset(next: AuditLogFilters): Promise<void> {
    const current = ++generation;
    filters = next;
    maxId = undefined;
    loading.value = true;
    try {
      const { data } = await auditApi.getAuditEvents({
        ...filters,
        limit: pageSize,
        offset: 0,
      });
      if (current !== generation) return;
      events.value = data.items;
      total.value = data.total;
      maxId = data.max_id ?? undefined;
    } catch (error) {
      // What's on screen was matched by the old filters, so it can't stay.
      if (current === generation) {
        events.value = [];
        total.value = 0;
      }
      throw error;
    } finally {
      if (current === generation) loading.value = false;
    }
  }

  async function loadMore(): Promise<void> {
    if (loading.value || loadingMore.value || !hasMore.value) return;
    const current = generation;
    loadingMore.value = true;
    try {
      const { data } = await auditApi.getAuditEvents({
        ...filters,
        maxId,
        limit: pageSize,
        offset: events.value.length,
      });
      if (current !== generation) return;
      events.value = [...events.value, ...data.items];
      total.value = data.total;
    } finally {
      loadingMore.value = false;
    }
  }

  return { events, total, loading, loadingMore, hasMore, reset, loadMore };
}
