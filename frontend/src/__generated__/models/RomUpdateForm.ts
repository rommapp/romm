/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type RomUpdateForm = {
    /**
     * IGDB game ID.
     */
    igdb_id?: (string | null);
    /**
     * SteamGridDB game ID.
     */
    sgdb_id?: (string | null);
    /**
     * MobyGames game ID.
     */
    moby_id?: (string | null);
    /**
     * ScreenScraper game ID.
     */
    ss_id?: (string | null);
    /**
     * RetroAchievements game ID.
     */
    ra_id?: (string | null);
    /**
     * LaunchBox game ID.
     */
    launchbox_id?: (string | null);
    /**
     * Hasheous game ID.
     */
    hasheous_id?: (string | null);
    /**
     * TheGamesDB game ID.
     */
    tgdb_id?: (string | null);
    /**
     * Flashpoint game ID.
     */
    flashpoint_id?: (string | null);
    /**
     * HowLongToBeat game ID.
     */
    hltb_id?: (string | null);
    /**
     * Demozoo production ID.
     */
    demozoo_id?: (string | null);
    /**
     * Pouët production ID.
     */
    pouet_id?: (string | null);
    /**
     * CSDb release ID.
     */
    csdb_id?: (string | null);
    /**
     * Steam app ID.
     */
    steam_id?: (string | null);
    /**
     * Libretro thumbnail ID.
     */
    libretro_id?: (string | null);
    /**
     * Raw IGDB metadata, as a JSON string.
     */
    raw_igdb_metadata?: (string | null);
    /**
     * Raw MobyGames metadata, as a JSON string.
     */
    raw_moby_metadata?: (string | null);
    /**
     * Raw ScreenScraper metadata, as a JSON string.
     */
    raw_ss_metadata?: (string | null);
    /**
     * Raw LaunchBox metadata, as a JSON string.
     */
    raw_launchbox_metadata?: (string | null);
    /**
     * Raw Hasheous metadata, as a JSON string.
     */
    raw_hasheous_metadata?: (string | null);
    /**
     * Raw Flashpoint metadata, as a JSON string.
     */
    raw_flashpoint_metadata?: (string | null);
    /**
     * Raw HowLongToBeat metadata, as a JSON string.
     */
    raw_hltb_metadata?: (string | null);
    /**
     * Raw Demozoo metadata, as a JSON string.
     */
    raw_demozoo_metadata?: (string | null);
    /**
     * Raw Pouët metadata, as a JSON string.
     */
    raw_pouet_metadata?: (string | null);
    /**
     * Raw CSDb metadata, as a JSON string.
     */
    raw_csdb_metadata?: (string | null);
    /**
     * Raw Steam metadata, as a JSON string.
     */
    raw_steam_metadata?: (string | null);
    /**
     * Raw manual metadata, as a JSON string.
     */
    raw_manual_metadata?: (string | null);
    name?: (string | null);
    /**
     * A custom sort key, used instead of the one derived from the name.
     */
    name_sort_key?: (string | null);
    summary?: (string | null);
    /**
     * The new name of the file or folder.
     */
    fs_name?: (string | null);
    url_cover?: (string | null);
    url_manual?: (string | null);
};

