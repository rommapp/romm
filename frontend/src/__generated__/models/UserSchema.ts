/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { Role } from './Role';

export type UserSchema = {
    id: number;
    username: string;
    enabled: boolean;
    role: Role;
    oauth_scopes: Array<string>;
    avatar_path: string;
};

