/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type RomMameMetadata = {
    set_name?: string;
    set_type?: 'parent' | 'clone' | 'bios' | 'device';
    cloneof?: string;
    romof?: string;
    is_mechanical?: boolean;
    status?: string;
    sourcefile?: string;
    players?: number;
    first_release_date?: number;
    year?: string;
    companies?: Array<string>;
    genres?: Array<string>;
    mame_build?: string;
};

