/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Why two games were linked, e.g. {"facet": "franchise", "value": "Metroid"}.
 *
 * `facet` is one of the metadata facets the engine scores on (genre,
 * franchise, collection, company, game_mode, decade), or "igdb" when the
 * link came from IGDB's own related-games list, or "top_rated" for the
 * cold-start feed. The frontend maps it to a translated label.
 */
export type SimilarityReasonSchema = {
    facet: string;
    value: string;
};

