/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PermAction } from './PermAction';
import type { PermEntity } from './PermEntity';
/**
 * A single (entity, action) grant on a group, with the own-only flag.
 */
export type GrantSchemaIO = {
    entity: PermEntity;
    action: PermAction;
    own_only?: boolean;
};

