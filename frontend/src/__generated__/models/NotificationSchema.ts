/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationActorSchema } from './NotificationActorSchema';
import type { NotificationKind } from './NotificationKind';
import type { NotificationLevel } from './NotificationLevel';
export type NotificationSchema = {
    id: number;
    kind: (NotificationKind | string);
    level: NotificationLevel;
    data: Record<string, any>;
    actor: (NotificationActorSchema | null);
    read_at: (string | null);
    created_at: string;
};

