// Stable media keys persisted in `rom_user.pinned_media`. Keep in sync with
// PINNED_MEDIA_KEY_PATTERN in backend/models/rom.py.
export const mediaKey = {
  scraped: (url: string) => `scraped:${url}`,
  file: (id: number) => `file:${id}`,
  screenshot: (id: number) => `screenshot:${id}`,
  artwork: (key: string) => `artwork:${key}`,
};
