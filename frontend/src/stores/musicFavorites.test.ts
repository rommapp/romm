import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import useMusicFavorites from "@/stores/musicFavorites";

const addFavorites = vi.fn();
const removeFavorites = vi.fn();

vi.mock("@/services/api/music", () => ({
  default: {
    addFavorites: (...args: unknown[]) => addFavorites(...args),
    removeFavorites: (...args: unknown[]) => removeFavorites(...args),
  },
}));

describe("music favorites store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    addFavorites.mockReset().mockResolvedValue({ data: { added: 1 } });
    removeFavorites.mockReset().mockResolvedValue({ data: { removed: 1 } });
  });

  it("seeds from a payload without forgetting tracks outside it", () => {
    const store = useMusicFavorites();
    store.merge([
      { rom_file_id: 1, is_favorite: true },
      { rom_file_id: 2, is_favorite: false },
    ]);
    store.merge([{ rom_file_id: 3, is_favorite: true }]);

    expect(store.isFavorite(1)).toBe(true);
    expect(store.isFavorite(2)).toBe(false);
    expect(store.isFavorite(3)).toBe(true);
    expect(store.count).toBe(2);
  });

  it("un-favorites a track that a later payload reports as not favorite", () => {
    const store = useMusicFavorites();
    store.merge([{ rom_file_id: 1, is_favorite: true }]);
    store.merge([{ rom_file_id: 1, is_favorite: false }]);
    expect(store.isFavorite(1)).toBe(false);
  });

  it("adds on the first toggle and removes on the second", async () => {
    const store = useMusicFavorites();

    await expect(store.toggle(4)).resolves.toBe(true);
    expect(addFavorites).toHaveBeenCalledWith({ rom_file_ids: [4] });
    expect(store.isFavorite(4)).toBe(true);

    await expect(store.toggle(4)).resolves.toBe(false);
    expect(removeFavorites).toHaveBeenCalledWith({ rom_file_ids: [4] });
    expect(store.isFavorite(4)).toBe(false);
  });

  it("leaves state untouched and reports null when the call fails", async () => {
    addFavorites.mockRejectedValue(new Error("boom"));
    const store = useMusicFavorites();

    await expect(store.toggle(5)).resolves.toBeNull();
    expect(store.isFavorite(5)).toBe(false);
    expect(store.isPending(5)).toBe(false);
  });

  it("ignores a second toggle while the first is still in flight", async () => {
    let release: () => void = () => {};
    addFavorites.mockImplementation(
      () => new Promise((resolve) => (release = () => resolve({ data: {} }))),
    );
    const store = useMusicFavorites();

    const first = store.toggle(6);
    expect(store.isPending(6)).toBe(true);
    await expect(store.toggle(6)).resolves.toBeNull();

    release();
    await first;
    expect(addFavorites).toHaveBeenCalledTimes(1);
    expect(store.isFavorite(6)).toBe(true);
  });
});
