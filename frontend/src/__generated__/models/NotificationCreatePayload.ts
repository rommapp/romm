/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NotificationLevel } from './NotificationLevel';
/**
 * A notification sent through the API, shown with its own title and body.
 */
export type NotificationCreatePayload = {
    title: string;
    body?: (string | null);
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
    data?: Record<string, any>;
    /**
     * Who to notify: a list of user IDs, `admins` or `all`. Null notifies only the caller. Only an admin can notify other users.
     */
    recipients?: (Array<number> | 'admins' | 'all' | null);
};

