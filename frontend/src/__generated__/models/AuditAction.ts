/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * What a user, or RomM itself, did; the client builds its sentence from `data`.
 */
export type AuditAction = 'rom.download' | 'rom.bulk_download' | 'rom.play' | 'rom.upload' | 'rom.create' | 'rom.edit' | 'rom.match' | 'rom.unmatch' | 'rom.delete' | 'rom.file_delete' | 'platform.create' | 'platform.edit' | 'platform.delete' | 'firmware.upload' | 'firmware.delete' | 'config.update' | 'collection.create' | 'collection.edit' | 'collection.delete' | 'collection.add_roms' | 'collection.remove_roms' | 'smart_collection.create' | 'smart_collection.edit' | 'smart_collection.delete' | 'scan.start' | 'scan.finish' | 'scan.stop' | 'task.run' | 'auth.login' | 'auth.login_failed' | 'auth.password_reset_request' | 'auth.password_reset' | 'user.create' | 'user.register' | 'user.edit' | 'user.delete' | 'user.permissions_edit' | 'permission_group.create' | 'permission_group.edit' | 'permission_group.delete' | 'visibility.hide' | 'visibility.unhide' | 'client_token.create' | 'client_token.regenerate' | 'client_token.revoke' | 'device.approve';
