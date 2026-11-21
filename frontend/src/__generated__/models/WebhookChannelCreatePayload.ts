/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationChannelMinLevel } from './NotificationChannelMinLevel';
import type { NotificationTopic } from './NotificationTopic';
export type WebhookChannelCreatePayload = {
    min_level?: NotificationChannelMinLevel;
    /**
     * The topics the channel forwards. Null forwards every topic.
     */
    topics?: (Array<NotificationTopic> | null);
    type: string;
    name: string;
    url: string;
    /**
     * The key the payload is signed with.
     */
    secret?: (string | null);
};

