import { describe, expect, it } from "vitest";
import { effectScope, nextTick, ref } from "vue";
import type { BrandingStatus } from "@/services/api/themeable";
import { useBrandingChoices } from "./index";

function statusWith(
  selected: string,
  packs: string[],
  random = { stock: false, built_in: true, accessibility: true },
): BrandingStatus {
  return {
    ok: true,
    selected,
    client: { stock_id: "none", random_id: "random" },
    packs: packs.map((id) => ({ id })),
    random,
  } as unknown as BrandingStatus;
}

function setup() {
  const status = ref<BrandingStatus | null>(null);
  const choices = effectScope().run(() => useBrandingChoices(status))!;
  return { status, ...choices };
}

describe("useBrandingChoices", () => {
  it("takes the saved theme and groups from the first status", async () => {
    const { status, selected, groups } = setup();
    status.value = statusWith("ember", ["ember", "neon"], {
      stock: true,
      built_in: false,
      accessibility: true,
    });
    await nextTick();
    expect(selected.value).toBe("ember");
    expect(groups.value).toEqual({
      stock: true,
      built_in: false,
      accessibility: true,
    });
  });

  it("keeps unsaved edits when a pack action refreshes the status", async () => {
    const { status, selected, groups } = setup();
    status.value = statusWith("ember", ["ember", "neon"]);
    await nextTick();
    selected.value = "neon";
    groups.value = { ...groups.value, built_in: false };

    status.value = statusWith("ember", ["ember", "neon", "dusk"]);
    await nextTick();
    expect(selected.value).toBe("neon");
    expect(groups.value.built_in).toBe(false);
  });

  it("falls back to RomM default when the chosen pack is deleted", async () => {
    const { status, selected } = setup();
    status.value = statusWith("ember", ["ember", "neon"]);
    await nextTick();
    selected.value = "neon";
    status.value = statusWith("ember", ["ember"]);
    await nextTick();
    expect(selected.value).toBe("none");
  });

  it("takes the server's values again after a save", async () => {
    const { status, selected, groups, adoptNext } = setup();
    status.value = statusWith("ember", ["ember", "neon"]);
    await nextTick();
    selected.value = "neon";
    adoptNext();
    status.value = statusWith("random", ["ember", "neon"], {
      stock: true,
      built_in: true,
      accessibility: false,
    });
    await nextTick();
    expect(selected.value).toBe("random");
    expect(groups.value.accessibility).toBe(false);
  });
});
