/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RAProgression } from './RAProgression';
import type { Role } from './Role';
export type UserSchema = {
    id: number;
    username: string;
    email: (string | null);
    enabled: boolean;
    role: Role;
    oauth_scopes: Array<string>;
    avatar_path: string;
    last_login: (string | null);
    last_active: (string | null);
    ra_username?: (string | null);
    ra_progression?: (RAProgression | null);
    netplayid?: (string | null);
    ui_settings?: (Record<string, any> | null);
    created_at: string;
    updated_at: string;
};

