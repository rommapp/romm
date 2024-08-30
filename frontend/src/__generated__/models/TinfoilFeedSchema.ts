/* generated using openapi-typescript-codegen -- do no edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */

import type { TinfoilFeedFileSchema } from './TinfoilFeedFileSchema';
import type { TinfoilFeedTitleDBSchema } from './TinfoilFeedTitleDBSchema';

export type TinfoilFeedSchema = {
    files: Array<TinfoilFeedFileSchema>;
    directories: Array<string>;
    titledb?: Record<string, TinfoilFeedTitleDBSchema>;
    success?: string;
    error?: string;
};

