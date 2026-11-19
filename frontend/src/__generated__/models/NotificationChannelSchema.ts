/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationChannelMinLevel } from './NotificationChannelMinLevel';
import type { NotificationChannelType } from './NotificationChannelType';
import type { NotificationTopic } from './NotificationTopic';
export type NotificationChannelSchema = {
    /**
     * The internal ID of the channel.
     */
    id: number;
    /**
     * The kind of channel: `apprise`, `webhook` or `email`.
     */
    type: NotificationChannelType;
    /**
     * The name of the channel.
     */
    name: string;
    /**
     * Whether notifications are sent on the channel.
     */
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
    /**
     * The display name of the Apprise service.
     */
    service_name: (string | null);
    /**
     * The Apprise service's settings, without its secrets.
     */
    fields: (Record<string, (boolean | number | string | Array<string>)> | null);
    /**
     * The names of the secret settings that are stored.
     */
    stored_secrets: (Array<string> | null);
    /**
     * Whether the channel has a secret stored.
     */
    has_secret: boolean;
    /**
     * Whether the channel is confirmed. A new email address has to be confirmed with a code first.
     */
    confirmed: boolean;
    /**
     * When a notification was last delivered on the channel.
     */
    last_delivered_at: (string | null);
    /**
     * The error from the last failed delivery, if any.
     */
    last_error: (string | null);
    /**
     * The number of deliveries that failed in a row.
     */
    consecutive_failures: number;
    /**
     * When the channel was created.
     */
    created_at: string;
};

