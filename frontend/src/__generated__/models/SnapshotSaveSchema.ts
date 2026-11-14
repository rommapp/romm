/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SaveFormat } from './SaveFormat';
import type { SaveShape } from './SaveShape';
import type { ScreenshotRefSchema } from './ScreenshotRefSchema';
export type SnapshotSaveSchema = {
    id: number;
    file_name: string;
    file_size_bytes: number;
    content_hash: (string | null);
    identity_hash: (string | null);
    shape: (SaveShape | null);
    format: (SaveFormat | null);
    emulator: (string | null);
    emulator_version: (string | null);
    core: (string | null);
    core_version: (string | null);
    download_path: string;
    screenshot: (ScreenshotRefSchema | null);
};

