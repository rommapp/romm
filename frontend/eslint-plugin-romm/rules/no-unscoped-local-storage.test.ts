import rule from "./no-unscoped-local-storage.js";
import { ruleTester } from "./testing";

const composable = { messageId: "composable" };
const global = { messageId: "global" };

ruleTester.run("no-unscoped-local-storage", rule, {
  valid: [
    'import { useUserLocalStorage } from "@/composables/useUserLocalStorage";',
    'import { useSessionStorage, useDebounceFn } from "@vueuse/core";',
    'import { useLocalStorage } from "./mine";',
    'userStorage.getItem("key");',
    'sessionStorage.setItem("key", "1");',
    'function f(localStorage) { return localStorage.getItem("key"); }',
    "const store = { localStorage: 1 }; store.localStorage;",
  ],
  invalid: [
    {
      code: 'import { useLocalStorage } from "@vueuse/core";',
      errors: [{ ...composable, data: { name: "useLocalStorage" } }],
    },
    {
      code: 'import { useStorage as keep, watchDebounced } from "@vueuse/core";',
      errors: [{ ...composable, data: { name: "useStorage" } }],
    },
    { code: 'localStorage.getItem("key");', errors: [global] },
    { code: 'window.localStorage.setItem("key", "1");', errors: [global] },
    { code: "globalThis.localStorage.clear();", errors: [global] },
    { code: 'useStorage("key", 1, localStorage);', errors: [global] },
  ],
});
