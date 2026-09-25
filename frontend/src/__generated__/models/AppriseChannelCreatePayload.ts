/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationChannelMinLevel } from './NotificationChannelMinLevel';
import type { NotificationTopic } from './NotificationTopic';
export type AppriseChannelCreatePayload = {
    min_level?: NotificationChannelMinLevel;
    topics?: (Array<NotificationTopic> | null);
    type: string;
    name: string;
    service: string;
    fields: Record<string, (boolean | number | string | Array<string>)>;
};

