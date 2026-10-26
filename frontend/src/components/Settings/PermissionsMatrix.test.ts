import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { RCheckbox, type RCheckboxState } from "@/lib";
import OverridesMatrix from "./OverridesMatrix.vue";
import PermissionsMatrix from "./PermissionsMatrix.vue";

vi.mock("vue-i18n");

// Per-cell checkboxes carry `states`; the column select-alls don't.
function cellStates(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents(RCheckbox)
    .filter((c) => c.props("states"))
    .map((c) => ({
      values: (c.props("states") as RCheckboxState[]).map((s) => s.value),
      current: c.props("stateValue"),
    }));
}

describe("PermissionsMatrix", () => {
  it("offers own only on entities with an owner", () => {
    const wrapper = mount(PermissionsMatrix, {
      props: {
        modelValue: [{ entity: "users", action: "write", own_only: true }],
        entities: ["users", "collections"],
        ownableEntities: ["collections"],
        actions: ["write"],
      },
    });

    // A stored own-only grant without an owner reads as the full grant it is.
    expect(cellStates(wrapper)).toEqual([
      { values: ["none", "full"], current: "full" },
      { values: ["none", "full", "own"], current: "none" },
    ]);
  });
});

describe("OverridesMatrix", () => {
  it("offers grant-own only on entities with an owner", () => {
    const wrapper = mount(OverridesMatrix, {
      props: {
        modelValue: [],
        entities: ["tasks", "devices"],
        ownableEntities: ["devices"],
        actions: ["write"],
      },
    });

    expect(cellStates(wrapper).map((c) => c.values)).toEqual([
      ["inherit", "grant", "revoke"],
      ["inherit", "grant", "grant_own", "revoke"],
    ]);
  });
});
