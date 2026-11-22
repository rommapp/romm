/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { FirmwareSchema } from './FirmwareSchema';
/**
 * A platform: a console, handheld or other system with roms in the library.
 */
export type PlatformSchema = {
    id: number;
    /**
     * The canonical slug, such as `snes`.
     */
    slug: string;
    /**
     * The name of the platform's folder in the library.
     */
    fs_slug: string;
    /**
     * The number of roms on the platform that the caller can see.
     */
    rom_count: number;
    name: string;
    igdb_slug: (string | null);
    moby_slug: (string | null);
    hltb_slug: (string | null);
    libretro_slug: (string | null);
    /**
     * A custom name the user set for the platform.
     */
    custom_name?: (string | null);
    description?: (string | null);
    igdb_id?: (number | null);
    /**
     * The SteamGridDB ID of the platform, used to find artwork.
     */
    sgdb_id?: (number | null);
    moby_id?: (number | null);
    launchbox_id?: (number | null);
    ss_id?: (number | null);
    ra_id?: (number | null);
    hasheous_id?: (number | null);
    tgdb_id?: (number | null);
    flashpoint_id?: (number | null);
    category?: (string | null);
    generation?: (number | null);
    first_release_year?: (number | null);
    family_name?: (string | null);
    family_slug?: (string | null);
    /**
     * The URL of a web page about the platform.
     */
    url?: (string | null);
    url_logo?: (string | null);
    firmware?: Array<FirmwareSchema>;
    created_at: string;
    updated_at: string;
    /**
     * The total size of the platform's roms on disk, in bytes.
     */
    fs_size_bytes: number;
    /**
     * True when no provider has matched the platform.
     */
    is_unidentified: boolean;
    /**
     * True when at least one provider has matched the platform.
     */
    is_identified: boolean;
    missing_from_fs: boolean;
    /**
     * The custom name when set, otherwise the platform's name.
     */
    readonly display_name: string;
    /**
     * The short name of the platform.
     */
    readonly abbreviation: string;
    /**
     * Other names the platform is known by.
     */
    readonly alternative_names: Array<string>;
    /**
     * The number of firmware files, whether usable or not.
     */
    readonly firmware_count: number;
};

