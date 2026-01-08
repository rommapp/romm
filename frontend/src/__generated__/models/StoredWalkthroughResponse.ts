/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { WalkthroughFormat } from './WalkthroughFormat';
import type { WalkthroughSource } from './WalkthroughSource';
export type StoredWalkthroughResponse = {
    id: number;
    rom_id: number;
    url: string;
    title: (string | null);
    author: (string | null);
    source: WalkthroughSource;
    format: WalkthroughFormat;
    content: string;
    created_at: string;
    updated_at: string;
};

