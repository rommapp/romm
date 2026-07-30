/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SmbPlatformPermissionSchema } from './SmbPlatformPermissionSchema';
export type SmbUserSchema = {
    id: number;
    username: string;
    permissions: Array<SmbPlatformPermissionSchema>;
    created_at: string;
    updated_at: string;
};

