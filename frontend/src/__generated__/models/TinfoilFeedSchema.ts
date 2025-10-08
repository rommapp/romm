/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { TinfoilFeedFileSchema } from './TinfoilFeedFileSchema';
export type TinfoilFeedSchema = {
    files: Array<TinfoilFeedFileSchema>;
    directories: Array<string>;
    titledb?: Record<string, Record<string, any>>;
    success?: string;
    error?: string;
};

