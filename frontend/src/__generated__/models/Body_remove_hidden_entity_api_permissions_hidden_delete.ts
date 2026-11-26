/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PermEntity } from './PermEntity';
export type Body_remove_hidden_entity_api_permissions_hidden_delete = {
    entity: PermEntity;
    entity_id: number;
    /**
     * The user it was hidden from. Set exactly one of `user_id` and `group_id`.
     */
    user_id?: (number | null);
    /**
     * The group it was hidden from. Set exactly one of `user_id` and `group_id`.
     */
    group_id?: (number | null);
};

