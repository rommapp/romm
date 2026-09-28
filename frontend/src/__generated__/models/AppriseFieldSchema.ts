/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type AppriseFieldSchema = {
    key: string;
    label: string;
    type: 'string' | 'int' | 'float' | 'bool' | 'choice' | 'list';
    required: boolean;
    private: boolean;
    advanced: boolean;
    default: (boolean | number | string | Array<string> | null);
    values: (Array<string> | null);
    min: (number | null);
    max: (number | null);
};

