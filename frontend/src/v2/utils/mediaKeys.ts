// Stable keys for every piece of media a ROM page can show, persisted in
// `rom_user.pinned_media`. Kept in sync with the backend's
// PINNED_MEDIA_KEY_PATTERN.
export const mediaKey = {
  scraped: (url: string) => `scraped:${url}`,
  file: (id: number) => `file:${id}`,
  screenshot: (id: number) => `screenshot:${id}`,
  artwork: (key: string) => `artwork:${key}`,
};
