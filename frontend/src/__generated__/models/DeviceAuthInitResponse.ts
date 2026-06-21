/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DeviceAuthInitResponse = {
    device_code: string;
    user_code: string;
    /**
     * Relative web-UI path (/pair/device). The client joins it with the origin it was configured to reach; the server is origin-agnostic.
     */
    verification_path: string;
    /**
     * Same path with ?user_code= appended, for QR display.
     */
    verification_path_complete: string;
    expires_in: number;
    interval: number;
};

