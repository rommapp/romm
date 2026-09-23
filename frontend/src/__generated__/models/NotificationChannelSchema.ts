/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationChannelType } from './NotificationChannelType';
import type { NotificationLevel } from './NotificationLevel';
import type { NotificationTopic } from './NotificationTopic';
import type { WebhookFormat } from './WebhookFormat';
export type NotificationChannelSchema = {
    id: number;
    type: NotificationChannelType;
    name: string;
    enabled: boolean;
    min_level: NotificationLevel;
    topics: (Array<NotificationTopic> | null);
    target: string;
    format: (WebhookFormat | null);
    has_secret: boolean;
    confirmed: boolean;
    last_delivered_at: (string | null);
    last_error: (string | null);
    consecutive_failures: number;
    created_at: string;
};

