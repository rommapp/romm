/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { IGDBDlc } from './IGDBDlc';
import type { IGDBRelatedGame } from './IGDBRelatedGame';
import type { IGDBRomExpansion } from './IGDBRomExpansion';

export type IGDBMetadata = {
    total_rating: string;
    first_release_date: (number | null);
    genres: Array<string>;
    franchises: Array<string>;
    collections: Array<string>;
    companies: Array<string>;
    expansions: Array<IGDBRomExpansion>;
    dlcs: Array<IGDBDlc>;
    remasters: Array<IGDBRelatedGame>;
    remakes: Array<IGDBRelatedGame>;
    expanded_games: Array<IGDBRelatedGame>;
};

