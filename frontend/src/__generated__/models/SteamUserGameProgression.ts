/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SteamEarnedAchievement } from './SteamEarnedAchievement';
export type SteamUserGameProgression = {
    rom_steam_id: number;
    rtime_last_played: (number | null);
    playtime_forever: number;
    num_achievements: number;
    num_unlocked: number;
    earned_achievements: Array<SteamEarnedAchievement>;
};

