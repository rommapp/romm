/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type RomMetadataSchema = {
    /**
     * The internal ID of the rom.
     */
    rom_id: number;
    /**
     * The genres, merged from the matched providers.
     */
    genres: Array<string>;
    /**
     * The franchises, merged from the matched providers.
     */
    franchises: Array<string>;
    /**
     * The game collections the title belongs to, merged from the matched providers.
     */
    collections: Array<string>;
    /**
     * The companies involved, merged from the matched providers.
     */
    companies: Array<string>;
    /**
     * The publishers, merged from the matched providers.
     */
    publishers: Array<string>;
    /**
     * The developers, merged from the matched providers.
     */
    developers: Array<string>;
    /**
     * The game modes, merged from the matched providers.
     */
    game_modes: Array<string>;
    /**
     * The age ratings, merged from the matched providers.
     */
    age_ratings: Array<string>;
    /**
     * The player count, as text.
     */
    player_count: string;
    /**
     * The first release date, as a timestamp.
     */
    first_release_date: (number | null);
    /**
     * The average of the ratings the matched providers report.
     */
    average_rating: (number | null);
};

