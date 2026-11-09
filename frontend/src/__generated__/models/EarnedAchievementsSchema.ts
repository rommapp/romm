/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AchievementGameSchema } from './AchievementGameSchema';
import type { AchievementTypeCountsSchema } from './AchievementTypeCountsSchema';
/**
 * RetroAchievements progress for the visible library, including games still at 0%.
 */
export type EarnedAchievementsSchema = {
    linked: boolean;
    synced: boolean;
    earned: number;
    total: number;
    points_earned: number;
    points_total: number;
    earned_by_type: AchievementTypeCountsSchema;
    games: Array<AchievementGameSchema>;
};

