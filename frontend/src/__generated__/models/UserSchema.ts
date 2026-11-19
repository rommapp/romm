/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RAProgression } from './RAProgression';
import type { Role } from './Role';
export type UserSchema = {
    /**
     * The internal ID of the user.
     */
    id: number;
    /**
     * The username.
     */
    username: string;
    /**
     * The email address.
     */
    email: (string | null);
    /**
     * Whether the user can sign in.
     */
    enabled: boolean;
    /**
     * The role of the user: `admin` or `user`.
     */
    role: Role;
    /**
     * The ID of the user's permission group.
     */
    permission_group_id?: (number | null);
    /**
     * The OAuth scopes of the user.
     */
    oauth_scopes: Array<string>;
    /**
     * Whether the user has a password.
     */
    has_password: boolean;
    /**
     * Whether the email address comes from the OIDC provider.
     */
    email_managed_by_oidc: boolean;
    /**
     * The path to the user's avatar.
     */
    avatar_path: string;
    /**
     * When the user last signed in.
     */
    last_login: (string | null);
    /**
     * When the user was last active.
     */
    last_active: (string | null);
    /**
     * The user's RetroAchievements username.
     */
    ra_username?: (string | null);
    /**
     * The user's RetroAchievements progress.
     */
    ra_progression?: (RAProgression | null);
    /**
     * The user's interface settings.
     */
    ui_settings?: (Record<string, any> | null);
    /**
     * The ID of the device making the request, when there is one.
     */
    current_device_id?: (string | null);
    /**
     * When the user was created.
     */
    created_at: string;
    /**
     * When the user last changed.
     */
    updated_at: string;
};

