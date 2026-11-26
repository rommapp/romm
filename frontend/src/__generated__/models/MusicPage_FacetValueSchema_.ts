/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { FacetValueSchema } from './FacetValueSchema';
export type MusicPage_FacetValueSchema_ = {
    items: Array<FacetValueSchema>;
    /**
     * The number of items across all pages.
     */
    total: number;
    limit: number;
    /**
     * The number of items skipped before this page. For example, 144 for the third page of 72.
     */
    offset: number;
};

