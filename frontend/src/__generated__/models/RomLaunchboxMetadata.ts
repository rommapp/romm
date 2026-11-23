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
    publishers?: Array<string>;
    developers?: Array<string>;
    images?: Array<LaunchboxImage>;
    box2d_url?: string;
    box2d_back_url?: string;
    box2d_side_url?: string;
    box3d_url?: string;
    video_url?: string;
    box2d_path?: (string | null);
    box2d_back_path?: (string | null);
    box2d_side_path?: (string | null);
    box3d_path?: (string | null);
    video_path?: (string | null);
};

