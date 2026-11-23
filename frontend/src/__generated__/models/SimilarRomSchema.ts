/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SimilarityReasonSchema } from './SimilarityReasonSchema';
import type { SimpleRomSchema } from './SimpleRomSchema';
export type SimilarRomSchema = {
    rom: SimpleRomSchema;
    score: number;
    reasons: Array<SimilarityReasonSchema>;
};

