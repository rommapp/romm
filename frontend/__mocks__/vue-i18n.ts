import { ref } from "vue";

// Used by `vi.mock("vue-i18n")` with no factory: `t` echoes the key and params,
// so tests assert on which message a component asked for rather than its wording.
export const useI18n = () => ({
  t: (key: string, ...args: unknown[]) =>
    [key, ...args.map((arg) => JSON.stringify(arg))].join(":"),
  locale: ref("en_US"),
});
