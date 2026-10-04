// useUserLocalStorage: localStorage namespaced by the signed-in user, so people
// sharing a browser don't inherit each other's preferences.
//
// Deliberately free of store and API imports: RomM.vue and the plugins read
// it during bootstrap, and main.ts feeds it the user through setStorageUser.
import {
  useLocalStorage,
  type RemovableRef,
  type UseStorageOptions,
} from "@vueuse/core";
import { shallowRef, type MaybeRefOrGetter } from "vue";

const storageUserId = shallowRef<number | null>(null);

export function setStorageUser(userId: number | null): void {
  storageUserId.value = userId;
}

/**
 * The key `key` is stored under for the current user.
 *
 * Signed out, a key is stored as is. Signed in, the user's copy claims (and
 * clears) a value stored unscoped, so earlier choices carry over exactly once.
 */
export function userStorageKey(key: string): string {
  const userId = storageUserId.value;
  if (userId === null) return key;

  const scopedKey = `user:${userId}:${key}`;
  const unscoped = localStorage.getItem(key);
  if (unscoped !== null) {
    if (localStorage.getItem(scopedKey) === null) {
      localStorage.setItem(scopedKey, unscoped);
    }
    localStorage.removeItem(key);
  }
  return scopedKey;
}

export const userStorage = {
  getItem: (key: string): string | null =>
    localStorage.getItem(userStorageKey(key)),
  setItem: (key: string, value: string): void =>
    localStorage.setItem(userStorageKey(key), value),
  removeItem: (key: string): void =>
    localStorage.removeItem(userStorageKey(key)),
};

/** `useLocalStorage` that follows the signed-in user, rebinding on sign-in/out. */
export function useUserLocalStorage<T>(
  key: string,
  initialValue: MaybeRefOrGetter<T>,
  options?: UseStorageOptions<T>,
): RemovableRef<T> {
  return useLocalStorage<T>(() => userStorageKey(key), initialValue, options);
}
