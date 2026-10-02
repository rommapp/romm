// Used by `vi.mock("vue-i18n")` with no factory: `t` echoes the key, so tests
// assert on which message a component asked for rather than its wording.
export const useI18n = () => ({ t: (key: string) => key });
