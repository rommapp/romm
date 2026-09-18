import { describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { useSaveStateTabs } from "./index";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function makeSave(overrides: Partial<SaveSchema> = {}): SaveSchema {
  return { id: 1, file_name: "1.srm", ...overrides } as SaveSchema;
}

function state(emulator: string | null): StateSchema {
  return { id: 2, file_name: "2.state", emulator } as StateSchema;
}

describe("useSaveStateTabs", () => {
  it("counts every state when the core loads them all", () => {
    const { tabs } = useSaveStateTabs(
      [makeSave()],
      [state("snes9x"), state(null)],
      "snes9x",
    );

    expect(tabs.value.map((tab) => [tab.id, tab.badge])).toEqual([
      ["save", 1],
      ["state", 2],
    ]);
  });

  it("counts compatible states over the total for a mixed list", () => {
    const { tabs, allStatesCompatible } = useSaveStateTabs(
      [],
      [state("snes9x"), state("bsnes")],
      "snes9x",
    );

    expect(allStatesCompatible.value).toBe(false);
    expect(tabs.value[1].badge).toBe("1/2");
  });

  it("disables states another core wrote and follows the core", () => {
    const core = ref<string | null>("snes9x");
    const { stateDisabledReason, compatibleStates } = useSaveStateTabs(
      [],
      [state("bsnes")],
      core,
    );

    expect(stateDisabledReason(state("bsnes"))).toBe(
      "play.state-incompatible-core",
    );
    expect(stateDisabledReason(state("snes9x"))).toBeNull();

    core.value = "bsnes";
    expect(compatibleStates.value).toHaveLength(1);
    expect(stateDisabledReason(state("bsnes"))).toBeNull();
  });
});
