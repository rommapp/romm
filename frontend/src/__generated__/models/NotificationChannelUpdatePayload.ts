/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationChannelMinLevel } from './NotificationChannelMinLevel';
import type { NotificationTopic } from './NotificationTopic';
/**
 * The fields to change; a null `topics` forwards every topic, an empty `secret` drops it.
 */
export type NotificationChannelUpdatePayload = {
    name?: (string | null);
    enabled?: (boolean | null);
    min_level?: (NotificationChannelMinLevel | null);
    topics?: (Array<NotificationTopic> | null);
    url?: (string | null);
    secret?: (string | null);
    address?: (string | null);
    fields?: (Record<string, (boolean | number | string | Array<string>)> | null);
};

