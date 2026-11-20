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
    /**
     * The topics the channel forwards. Null forwards every topic.
     */
    topics: (Array<NotificationTopic> | null);
    /**
     * Where the channel sends: the URL with its secrets hidden, or an email address.
     */
    target: string;
    /**
     * The Apprise service ID, for an Apprise channel.
     */
    service: (string | null);
    service_name: (string | null);
    /**
     * The Apprise service's settings, without its secrets.
     */
    fields: (Record<string, (boolean | number | string | Array<string>)> | null);
    /**
     * The names of the secret settings that are stored.
     */
    stored_secrets: (Array<string> | null);
    has_secret: boolean;
    /**
     * Whether the channel is confirmed. A new email address has to be confirmed with a code first.
     */
    confirmed: boolean;
    last_delivered_at: (string | null);
    last_error: (string | null);
    consecutive_failures: number;
    created_at: string;
};

