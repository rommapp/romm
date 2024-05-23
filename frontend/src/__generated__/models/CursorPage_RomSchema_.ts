/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { RomSchema } from './RomSchema';

export type CursorPage_RomSchema_ = {
    items: Array<RomSchema>;
    /**
     * Total items
     */
    total?: (number | null);
    /**
     * Cursor to refetch the current page
     */
    current_page?: (string | null);
    /**
     * Cursor to refetch the current page starting from the last item
     */
    current_page_backwards?: (string | null);
    /**
     * Cursor for the previous page
     */
    previous_page?: (string | null);
    /**
     * Cursor for the next page
     */
    next_page?: (string | null);
};

