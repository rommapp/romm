/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationLevel } from './NotificationLevel';
import type { NotificationTopic } from './NotificationTopic';
import type { WebhookFormat } from './WebhookFormat';
/**
 * The fields to change; a null `topics` forwards every topic, an empty `secret` drops it.
 */
export type NotificationChannelUpdatePayload = {
    name?: (string | null);
    enabled?: (boolean | null);
    min_level?: (NotificationLevel | null);
    topics?: (Array<NotificationTopic> | null);
    url?: (string | null);
    format?: (WebhookFormat | null);
    secret?: (string | null);
    address?: (string | null);
};

