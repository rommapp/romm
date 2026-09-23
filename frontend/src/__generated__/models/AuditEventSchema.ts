/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AuditAction } from './AuditAction';
import type { AuditActorKind } from './AuditActorKind';
import type { AuditCategory } from './AuditCategory';
import type { NotificationActorSchema } from './NotificationActorSchema';
export type AuditEventSchema = {
    id: number;
    action: (AuditAction | string);
    category: (AuditCategory | null);
    occurred_at: string;
    actor_kind: AuditActorKind;
    actor: (NotificationActorSchema | null);
    actor_name: (string | null);
    target_type: (string | null);
    target_id: (string | null);
    target_name: (string | null);
    ip_address: (string | null);
    device_id: (string | null);
    device_name: (string | null);
    data: Record<string, any>;
};

