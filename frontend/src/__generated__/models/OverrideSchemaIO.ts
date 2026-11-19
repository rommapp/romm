/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PermAction } from './PermAction';
import type { PermEntity } from './PermEntity';
export type OverrideSchemaIO = {
    /**
     * The kind of thing the override covers.
     */
    entity: PermEntity;
    /**
     * The action the override applies to.
     */
    action: PermAction;
    /**
     * True grants the action and false denies it.
     */
    granted: boolean;
    /**
     * Whether the override covers only things the user owns.
     */
    own_only?: boolean;
};

