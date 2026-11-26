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
     * The highest ID among the matching events. Pass it as `max_id` when requesting later pages, so they page through the same set of events.
     */
    max_id?: (number | null);
};

