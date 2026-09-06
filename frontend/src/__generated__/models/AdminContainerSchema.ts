/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ContainerSessionSchema } from './ContainerSessionSchema';
export type AdminContainerSchema = {
    container: string;
    label?: (string | null);
    host: string;
    platforms: Array<string>;
    supports_desktop: boolean;
    configured: boolean;
    session?: (ContainerSessionSchema | null);
};

