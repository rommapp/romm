/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MemoryCardSummarySchema } from './MemoryCardSummarySchema';
/**
 * The 428 body: a container still holds a card nobody has decided about.
 *
 * The claim is not held open behind the prompt; the answer comes back on a
 * fresh claim as `card_import`.
 */
export type MemoryCardImportRequired = {
    code: string;
    outcome: 'found' | 'unreadable';
    summary?: (MemoryCardSummarySchema | null);
    reason?: (string | null);
};

