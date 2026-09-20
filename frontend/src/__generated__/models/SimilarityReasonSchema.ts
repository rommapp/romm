/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Facet } from './Facet';
/**
 * Why two games were linked, e.g. {"facet": "franchise", "value": "Metroid"}.
 *
 * `value` is empty for facets with no value of their own, which the frontend
 * renders as a translated phrase instead.
 */
export type SimilarityReasonSchema = {
    facet: Facet;
    value: string;
};

