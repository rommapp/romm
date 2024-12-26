/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

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
    created_at: string;
    updated_at: string;
};

