/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type RomResolveRequest = {
    /**
     * Canonical platform slug.
     */
    platform_slug: string;
    /**
     * Client-side ROM filename.
     */
    fs_name: string;
    /**
     * CRC32 hash of the ROM.
     */
    crc_hash?: (string | null);
    /**
     * MD5 hash of the ROM.
     */
    md5_hash?: (string | null);
    /**
     * SHA1 hash of the ROM.
     */
    sha1_hash?: (string | null);
    /**
     * Display name hint.
     */
    name?: (string | null);
};

