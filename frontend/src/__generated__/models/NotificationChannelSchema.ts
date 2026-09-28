/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationChannelMinLevel } from './NotificationChannelMinLevel';
import type { NotificationChannelType } from './NotificationChannelType';
import type { NotificationTopic } from './NotificationTopic';
export type NotificationChannelSchema = {
    id: number;
    type: NotificationChannelType;
    name: string;
    enabled: boolean;
    min_level: NotificationChannelMinLevel;
    topics: (Array<NotificationTopic> | null);
    target: string;
    service: (string | null);
    service_name: (string | null);
    fields: (Record<string, (boolean | number | string | Array<string>)> | null);
    stored_secrets: (Array<string> | null);
    has_secret: boolean;
    confirmed: boolean;
    last_delivered_at: (string | null);
    last_error: (string | null);
    consecutive_failures: number;
    created_at: string;
};

