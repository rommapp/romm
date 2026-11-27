// URLs that already decoded this session, shared by every RImage so a
// remount does not paint the loading slot for a file already in memory.
export const decodedSrcs = new Set<string>();
