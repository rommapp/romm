/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Entity-type vocabulary for granular permissions.
 *
 * Mirrors the coarse scope domains (see ``handler/auth/constants.py``) so the
 * grant matrix can be projected back onto the legacy ``Scope`` set without
 * drift (see ``handler/auth/permissions_map.py``).
 */
export type PermEntity = 'platforms' | 'roms' | 'collections' | 'playlists' | 'firmware' | 'assets' | 'devices' | 'users' | 'tasks' | 'logs';
