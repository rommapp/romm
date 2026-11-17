/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ValkeyMemory } from './ValkeyMemory';
export type ValkeyStatus = {
    ok: boolean;
    latency_ms: number;
    error: ('timeout' | 'unreachable' | 'error' | 'no_workers' | 'behind' | 'ahead' | 'unreadable' | 'unwritable' | null);
    memory: (ValkeyMemory | null);
};

