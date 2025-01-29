/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { IGDBAgeRating } from './IGDBAgeRating';
import type { IGDBMetadataPlatform } from './IGDBMetadataPlatform';
import type { IGDBRelatedGame } from './IGDBRelatedGame';
export type RomIGDBMetadata = {
    total_rating?: string;
    aggregated_rating?: string;
    first_release_date?: (number | null);
    youtube_video_id?: (string | null);
    genres?: Array<string>;
    franchises?: Array<string>;
    alternative_names?: Array<string>;
    collections?: Array<string>;
    companies?: Array<string>;
    game_modes?: Array<string>;
    age_ratings?: Array<IGDBAgeRating>;
    platforms?: Array<IGDBMetadataPlatform>;
    expansions?: Array<IGDBRelatedGame>;
    dlcs?: Array<IGDBRelatedGame>;
    remasters?: Array<IGDBRelatedGame>;
    remakes?: Array<IGDBRelatedGame>;
    expanded_games?: Array<IGDBRelatedGame>;
    ports?: Array<IGDBRelatedGame>;
    similar_games?: Array<IGDBRelatedGame>;
};

