/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ClientTokenCreateSchema = {
    id: number;
    name: string;
    scopes: Array<string>;
    expires_at: (string | null);
    last_used_at: (string | null);
    created_at: string;
    user_id: number;
    raw_token: string;
};

