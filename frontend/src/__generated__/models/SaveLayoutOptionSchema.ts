/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * A core option a layout's files read. `values` is empty for a free-form
 * value; a `default` of "" means the files need the option set.
 */
export type SaveLayoutOptionSchema = {
    key: string;
    /**
     * The allowed values. Empty for a free-form value.
     */
    values: Array<string>;
    /**
     * The default value. Empty when the option has no default and must be set.
     */
    default: string;
};

