/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationLevel } from './NotificationLevel';
import type { NotificationTopic } from './NotificationTopic';
import type { WebhookFormat } from './WebhookFormat';
export type WebhookChannelCreatePayload = {
    min_level?: NotificationLevel;
    topics?: (Array<NotificationTopic> | null);
    type: string;
    name: string;
    url: string;
    format?: WebhookFormat;
    secret?: (string | null);
};

