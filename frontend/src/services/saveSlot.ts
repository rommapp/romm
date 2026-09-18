// Slot names and limits shared by UI and the save client. Keep this file
// free of axios so presentational code can import it without the API graph.

export const AUTOSAVE_SLOT = "autosave";

// Mirrors backend models.assets.SAVE_SLOT_MAX_LENGTH.
export const SAVE_SLOT_MAX_LENGTH = 255;

// A keepalive request outlives its document; browsers cap the body at 64 KB.
export const UNLOAD_SAVE_MAX_BYTES = 60 * 1024;
