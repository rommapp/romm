/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RomFiltersDict } from './RomFiltersDict';
import type { SimpleRomSchema } from './SimpleRomSchema';
export type CustomLimitOffsetPage_SimpleRomSchema_ = {
    items: Array<SimpleRomSchema>;
    total: number;
    limit: number;
    offset: number;
    char_index: Record<string, number>;
    rom_id_index: Array<number>;
    filter_values: RomFiltersDict;
};

