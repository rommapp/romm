/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type UserNoteSchema = {
    id: number;
    title: string;
    content: string;
    is_public: boolean;
    tags?: Array<string> | null;
    metadata?: Record<string, any> | null;
    shared_with_users?: Array<number> | null;
    collaboration_level?: string | null;
    created_at: string;
    updated_at: string;
    user_id: number;
    username: string;
};

