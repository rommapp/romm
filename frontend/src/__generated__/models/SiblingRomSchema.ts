/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SiblingRomSchema = {
    id: number;
    name: (string | null);
    /**
     * The file name without its extension or any tags in parentheses or brackets.
     */
    fs_name_no_tags: string;
    /**
     * The file name without its extension. Tags are kept.
     */
    fs_name_no_ext: string;
    /**
     * Whether the user chose this version as the main one.
     */
    is_main_sibling: boolean;
    /**
     * The lowercase name the versions are sorted by.
     */
    readonly sort_comparator: string;
};

