/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type RomMetadataSchema = {
    rom_id: number;
    genres: Array<string>;
    franchises: Array<string>;
    /**
     * The game collections the title belongs to, merged from the matched providers.
     */
    collections: Array<string>;
    companies: Array<string>;
    publishers: Array<string>;
    developers: Array<string>;
    game_modes: Array<string>;
    age_ratings: Array<string>;
    player_count: string;
    /**
     * The first release date, as a Unix timestamp in milliseconds.
     */
    first_release_date: (number | null);
    /**
     * The average of the ratings the matched providers report.
     */
    average_rating: (number | null);
};

