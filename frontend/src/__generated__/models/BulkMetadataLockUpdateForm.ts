/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type BulkMetadataLockUpdateForm = {
    fields: Array<'name' | 'summary' | 'cover' | 'screenshots' | 'manual' | 'genres' | 'franchises' | 'collections' | 'companies' | 'game_modes' | 'age_ratings' | 'first_release_date' | 'player_count'>;
    locked: boolean;
    platform_id?: (number | null);
    all?: boolean;
};
