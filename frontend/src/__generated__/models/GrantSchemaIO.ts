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
    /**
     * The kind of thing the grant covers.
     */
    entity: PermEntity;
    /**
     * The action the grant allows.
     */
    action: PermAction;
    /**
     * Whether the grant covers only things the user owns.
     */
    own_only?: boolean;
};

