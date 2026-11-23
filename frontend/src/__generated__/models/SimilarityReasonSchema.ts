/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Facet } from './Facet';
/**
 * Why two games were linked, e.g. {"facet": "franchise", "value": "Example Series"}.
 *
 * `value` is empty for facets with no value of their own, which the frontend
 * renders as a translated phrase instead.
 */
export type SimilarityReasonSchema = {
    /**
     * The kind of thing the two games share, such as `franchise`.
     */
    facet: Facet;
    /**
     * The shared value, such as the franchise name. Empty for facets that have no value.
     */
    value: string;
};

