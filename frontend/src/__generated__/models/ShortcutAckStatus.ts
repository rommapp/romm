/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Outcome a launcher client reports for one queued shortcut.
 */
export type ShortcutAckStatus = {
    /**
     * Lifecycle outcome; removed deletes the row.
     */
    status: 'staged' | 'added' | 'failed' | 'removed';
    steam_app_id?: (number | null);
    error?: (string | null);
};

