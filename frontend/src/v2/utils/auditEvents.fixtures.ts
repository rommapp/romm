import type { AuditEventSchema } from "@/__generated__";

export function makeAuditEvent(
  overrides: Partial<AuditEventSchema> = {},
): AuditEventSchema {
  return {
    id: 1,
    action: "rom.download",
    category: null,
    occurred_at: "2026-09-24T10:00:00Z",
    actor_kind: "user",
    actor: null,
    actor_name: "zurdi",
    target_type: "rom",
    target_id: "12",
    target_name: "Metroid",
    ip_address: null,
    device_id: null,
    device_name: null,
    data: {},
    ...overrides,
  };
}
