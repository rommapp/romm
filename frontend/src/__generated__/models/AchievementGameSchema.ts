/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AchievementTypeCountsSchema } from './AchievementTypeCountsSchema';
import type { CatalogAchievementSchema } from './CatalogAchievementSchema';
export type AchievementGameSchema = {
    rom_id: number;
    name: string;
    platform_name: (string | null);
    platform_slug?: (string | null);
    platform_fs_slug?: (string | null);
    cover_url: (string | null);
    path_cover_large?: (string | null);
    path_cover_small?: (string | null);
    url_cover?: (string | null);
    title_url: (string | null);
    ingame_url: (string | null);
    box_art_url: (string | null);
    earned: number;
    total: number;
    points_earned: number;
    points_total: number;
    earned_by_type: AchievementTypeCountsSchema;
    achievements: Array<CatalogAchievementSchema>;
};

