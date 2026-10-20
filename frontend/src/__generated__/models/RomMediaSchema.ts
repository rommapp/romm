/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type RomMediaSchema = {
    /**
     * Media kind: a MetadataMediaType value, 'cover_large' or 'cover_small', or 'image'/'video' for a library file.
     */
    type: string;
    /**
     * Where the file came from: a metadata source ('ss', 'gamelist', 'launchbox'), 'romm' for the rom's own cover, manual and screenshots, or 'library' for a file next to the rom.
     */
    source: string;
    /**
     * Server path the file is served from.
     */
    path: string;
    size_bytes: number;
    /**
     * Lowercase file extension.
     */
    format: (string | null);
    /**
     * The disc a per-disc file shows.
     */
    disc: (number | null);
    /**
     * Position among the rom's screenshots.
     */
    index: (number | null);
    /**
     * The rom file a library entry is.
     */
    file_id: (number | null);
    /**
     * MD5 of a library file, when hashed.
     */
    md5: (string | null);
    /**
     * A higher-priority source holds the same kind and disc, so RomM shows that copy instead.
     */
    shadowed: boolean;
};

