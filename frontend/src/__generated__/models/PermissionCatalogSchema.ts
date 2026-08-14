/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PermAction } from './PermAction';
import type { PermEntity } from './PermEntity';
/**
 * The vocabulary the admin UI renders the group/override matrix from.
 */
export type PermissionCatalogSchema = {
    entities: Array<PermEntity>;
    actions: Array<PermAction>;
};

