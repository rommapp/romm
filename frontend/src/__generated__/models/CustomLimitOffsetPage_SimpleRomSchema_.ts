/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SimpleRomSchema } from './SimpleRomSchema';
export type CustomLimitOffsetPage_SimpleRomSchema_ = {
    items: Array<SimpleRomSchema>;
    /**
     * The number of roms across all pages. Null when `with_total` is false, unless `with_rom_id_index` is true.
     */
    total: (number | null);
    limit: number;
    /**
     * The number of items skipped before this page. For example, 144 for the third page of 72.
     */
    offset: number;
    /**
     * For each first letter, the position in the full result where roms starting with it begin. Empty when `with_char_index` is false, the sort is not alphabetical, or a search ranks by relevance.
     */
    char_index: Record<string, number>;
    /**
     * The IDs of every matching rom, in order. Empty when `with_rom_id_index` is false.
     */
    rom_id_index: Array<number>;
};

