/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WalkthroughFormat } from './WalkthroughFormat';
import type { WalkthroughSource } from './WalkthroughSource';
export type WalkthroughResponse = {
    url: string;
    title?: (string | null);
    author?: (string | null);
    source: WalkthroughSource;
    format: WalkthroughFormat;
    content: string;
};

