/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationChannelMinLevel } from './NotificationChannelMinLevel';
import type { NotificationTopic } from './NotificationTopic';
import type { WebhookFormat } from './WebhookFormat';
export type WebhookChannelCreatePayload = {
    min_level?: NotificationChannelMinLevel;
    topics?: (Array<NotificationTopic> | null);
    type: string;
    name: string;
    url: string;
    format?: WebhookFormat;
    secret?: (string | null);
};

