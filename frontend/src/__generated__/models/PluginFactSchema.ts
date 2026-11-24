/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PluginFactGroupSchema } from './PluginFactGroupSchema';
/**
 * A plugin's panel, filled with what its source answered.
 *
 * `note` carries why a panel is empty: a title nobody has reported on, a
 * source that timed out, a manifest whose paths no longer match. It is said
 * rather than raised, because a compatibility lookup failing is not a reason
 * to break the page it sits on.
 */
export type PluginFactSchema = {
    id: string;
    label: string;
    slot?: 'game.details' | 'game.play' | 'app.nav' | 'settings.page';
    link?: (string | null);
    groups?: Array<PluginFactGroupSchema>;
    total?: number;
    note?: (string | null);
    scope?: (string | null);
};

