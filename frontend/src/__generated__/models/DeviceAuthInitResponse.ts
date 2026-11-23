/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DeviceAuthInitResponse = {
    /**
     * The secret code the device polls with.
     */
    device_code: string;
    /**
     * The short code the user enters or scans to approve the device.
     */
    user_code: string;
    /**
     * Relative web-UI path (/pair/device). The client joins it with the origin it was configured to reach; the server is origin-agnostic.
     */
    verification_path: string;
    /**
     * Same path with ?user_code= appended, for QR display.
     */
    verification_path_complete: string;
    /**
     * How long the codes stay valid, in seconds.
     */
    expires_in: number;
    /**
     * How often the device should poll, in seconds.
     */
    interval: number;
};

