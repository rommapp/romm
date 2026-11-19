/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MusicGameFacetSchema } from './MusicGameFacetSchema';
export type MusicPage_MusicGameFacetSchema_ = {
    /**
     * The items on this page.
     */
    items: Array<MusicGameFacetSchema>;
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
};

