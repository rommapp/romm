/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationLevel } from './NotificationLevel';
/**
 * A notification sent through the API, shown with its own title and body.
 */
export type NotificationCreatePayload = {
    /**
     * The title of the notification.
     */
    title: string;
    /**
     * The text of the notification.
     */
    body?: (string | null);
    /**
     * The level of the notification: `info`, `success`, `warning` or `error`. Defaults to `info`.
     */
    level?: NotificationLevel;
    /**
     * A label a client uses to tell its own notifications apart, such as `my_app.sync_done`.
     */
    kind?: string;
    /**
     * A path inside RomM, such as `/rom/12`.
     */
    link?: (string | null);
    /**
     * A Material Design Icons name, such as `mdi-sync`.
     */
    icon?: (string | null);
    /**
     * Extra data attached to the notification.
     */
    data?: Record<string, any>;
    /**
     * User ids, `admins` or `all`; only an admin may notify anyone but themselves. Null notifies the caller.
     */
    recipients?: (Array<number> | 'admins' | 'all' | null);
};

