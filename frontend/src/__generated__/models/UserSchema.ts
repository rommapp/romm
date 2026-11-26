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
    /**
     * Whether the user can sign in.
     */
    enabled: boolean;
    role: Role;
    permission_group_id?: (number | null);
    oauth_scopes: Array<string>;
    has_password: boolean;
    email_managed_by_oidc: boolean;
    avatar_path: string;
    last_login: (string | null);
    last_active: (string | null);
    ra_username?: (string | null);
    ra_progression?: (RAProgression | null);
    ui_settings?: (Record<string, any> | null);
    /**
     * The ID of the device making the request, when there is one.
     */
    current_device_id?: (string | null);
    created_at: string;
    updated_at: string;
};

