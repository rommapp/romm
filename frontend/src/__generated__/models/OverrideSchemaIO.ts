/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PermAction } from './PermAction';
import type { PermEntity } from './PermEntity';
export type OverrideSchemaIO = {
    entity: PermEntity;
    action: PermAction;
    granted: boolean;
    own_only?: boolean;
};

