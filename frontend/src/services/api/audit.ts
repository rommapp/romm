import type {
  AuditCategory,
  AuditPage_AuditEventSchema_,
} from "@/__generated__";
import api from "@/services/api";

export interface AuditEventsQuery {
  actorIds?: number[];
  categories?: AuditCategory[];
  since?: string;
  until?: string;
  search?: string;
  /** Pins later pages to the events the first page saw. */
  maxId?: number;
  limit?: number;
  offset?: number;
}

async function getAuditEvents(query: AuditEventsQuery = {}) {
  return api.get<AuditPage_AuditEventSchema_>("/audit-events", {
    params: {
      actor_id: query.actorIds,
      category: query.categories,
      since: query.since,
      until: query.until,
      search: query.search || undefined,
      max_id: query.maxId,
      limit: query.limit,
      offset: query.offset,
    },
  });
}

export default {
  getAuditEvents,
};
