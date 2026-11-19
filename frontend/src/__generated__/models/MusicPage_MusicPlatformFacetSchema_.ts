/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MusicPlatformFacetSchema } from './MusicPlatformFacetSchema';
export type MusicPage_MusicPlatformFacetSchema_ = {
    /**
     * The items on this page.
     */
    items: Array<MusicPlatformFacetSchema>;
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

