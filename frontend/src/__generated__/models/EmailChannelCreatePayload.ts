/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationLevel } from './NotificationLevel';
import type { NotificationTopic } from './NotificationTopic';
export type EmailChannelCreatePayload = {
    min_level?: NotificationLevel;
    topics?: (Array<NotificationTopic> | null);
    type: string;
    name: string;
    address: string;
};

