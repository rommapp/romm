/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ScreenshotRefSchema } from './ScreenshotRefSchema';
export type SnapshotStateSchema = {
    id: number;
    file_name: string;
    file_size_bytes: number;
    content_hash: (string | null);
    emulator_version: (string | null);
    core_version: (string | null);
    download_path: string;
    screenshot: (ScreenshotRefSchema | null);
};

