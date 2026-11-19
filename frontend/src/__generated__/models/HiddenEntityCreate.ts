/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PermEntity } from './PermEntity';
export type HiddenEntityCreate = {
    /**
     * The kind of entity to hide.
     */
    entity: PermEntity;
    /**
     * The ID of the entity to hide.
     */
    entity_id: number;
    /**
     * The user to hide it from. Set exactly one of `user_id` and `group_id`.
     */
    user_id?: (number | null);
    /**
     * The group to hide it from. Set exactly one of `user_id` and `group_id`.
     */
    group_id?: (number | null);
};

