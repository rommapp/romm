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
     * User ids, `admins` or `all`; only an admin may notify anyone but themselves. Null notifies the caller.
     */
    recipients?: (Array<number> | 'admins' | 'all' | null);
};

