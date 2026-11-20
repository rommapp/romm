/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AuditEventSchema } from './AuditEventSchema';
export type AuditPage_AuditEventSchema_ = {
    items: Array<AuditEventSchema>;
    /**
     * The number of items across all pages.
     */
    total: number;
    limit: number;
    /**
     * The number of items skipped before this page. For example, 144 for the third page of 72.
     */
    offset: number;
    /**
     * The highest ID among the matching events. Send it back as `max_id` to keep later pages on the same events.
     */
    max_id?: (number | null);
};

