/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A card's identity. Its data lives in `versions`; the list views return
 * the card without them (fetch history via the versions route) so the schema
 * never touches the lazy="raise" relationship.
 */
export type MemoryCardSchema = {
    id: number;
    user_id: number;
    emulator: string;
    platform_id?: (number | null);
    name: string;
    slot: number;
    is_public?: boolean;
    created_at: string;
    updated_at: string;
};

