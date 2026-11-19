/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AuditEventSchema } from './AuditEventSchema';
export type AuditPage_AuditEventSchema_ = {
    /**
     * The items on this page.
     */
    items: Array<AuditEventSchema>;
    /**
     * The number of items across all pages.
     */
    total: number;
    /**
     * The number of items per page, such as 72.
     */
    limit: number;
    /**
     * The number of items skipped before this page. For example, 144 for the third page of 72.
     */
    offset: number;
    /**
     * The highest event ID on the first page. Send it back as `max_id` to keep later pages on the same events.
     */
    max_id?: (number | null);
};

