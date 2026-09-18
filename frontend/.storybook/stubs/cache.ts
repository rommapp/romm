// Storybook-only: no Cache API / axios round-trips.

export async function init(): Promise<void> {}

export default {
  init,
  async get() {
    return undefined;
  },
  async set() {},
  async clear() {},
};
