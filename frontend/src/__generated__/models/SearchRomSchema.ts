/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

export type SearchRomSchema = {
    igdb_id: (number | null);
    name: (string | null);
    slug: (string | null);
    summary: (string | null);
    url_cover: string;
    url_screenshots: Array<string>;
    total_rating: (string | null);
    genres: Array<Record<string, any>>;
    franchises: Array<Record<string, any>>;
    collections: Array<Record<string, any>>;
    expansions: Array<Record<string, any>>;
    dlcs: Array<Record<string, any>>;
    remasters: Array<Record<string, any>>;
    remakes: Array<Record<string, any>>;
    expanded_games: Array<Record<string, any>>;
    companies: Array<Record<string, any>>;
    first_release_date: (number | null);
};

