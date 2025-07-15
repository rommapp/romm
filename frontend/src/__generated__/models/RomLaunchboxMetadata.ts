/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { LaunchboxImage } from './LaunchboxImage';
export type RomLaunchboxMetadata = {
    first_release_date?: (number | null);
    max_players?: number;
    release_type?: string;
    cooperative?: boolean;
    youtube_video_id?: string;
    community_rating?: number;
    community_rating_count?: number;
    wikipedia_url?: string;
    esrb?: string;
    genres?: Array<string>;
    companies?: Array<string>;
    images?: Array<LaunchboxImage>;
};

