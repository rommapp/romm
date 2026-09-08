/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SimilarityReasonSchema } from './SimilarityReasonSchema';
import type { SimpleRomSchema } from './SimpleRomSchema';
export type RecommendedRomSchema = {
    rom: SimpleRomSchema;
    score: number;
    reasons: Array<SimilarityReasonSchema>;
    seed_rom_id?: (number | null);
    seed_rom_name?: (string | null);
};

