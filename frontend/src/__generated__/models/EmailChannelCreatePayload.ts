/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationChannelMinLevel } from './NotificationChannelMinLevel';
import type { NotificationTopic } from './NotificationTopic';
export type EmailChannelCreatePayload = {
    min_level?: NotificationChannelMinLevel;
    /**
     * The topics the channel forwards. Null forwards every topic.
     */
    topics?: (Array<NotificationTopic> | null);
    type: string;
    name: string;
    /**
     * The email address notifications are sent to. A confirmation code is sent to it first.
     */
    address: string;
};

