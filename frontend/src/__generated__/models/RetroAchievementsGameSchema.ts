/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Achievements } from './Achievements';

export type RetroAchievementsGameSchema = {
    ID: number;
    Title: string;
    ConsoleID: number;
    ForumTopicID: number;
    Flags: number;
    ImageIcon: string;
    ImageTitle: string;
    ImageIngame: string;
    ImageBoxArt: string;
    Publisher: string;
    Developer: string;
    Genre: string;
    Released: string;
    IsFinal: number;
    RichPresencePatch: string;
    GuideURL?: (string | null);
    ConsoleName: string;
    NumDistinctPlayers: number;
    ParentGameID?: (string | null);
    NumAchievements: number;
    Achievements: Record<string, Achievements>;
    NumAwardedToUser: number;
    NumAwardedToUserHardcore: number;
    NumDistinctPlayersCasual: number;
    NumDistinctPlayersHardcore: number;
    ReleasedAtGranularity: string;
    UserCompletion: string;
    UserCompletionHardcore: string;
    HighestAwardKind?: (string | null);
    HighestAwardDate?: (string | null);
};

