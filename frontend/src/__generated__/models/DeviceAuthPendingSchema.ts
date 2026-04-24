/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DeviceAuthPendingSchema = {
    client_device_identifier: string;
    name: string;
    client: string;
    platform: (string | null);
    client_version: (string | null);
    requested_scopes: Array<string>;
    allowed_scopes: Array<string>;
    expires_at: string;
};
