import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MemoryCardSchema } from "@/__generated__";
import memoryCardApi from "@/services/api/memory-card";
import MemoryCardManager from "./MemoryCardManager.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/services/api/memory-card", () => ({
  default: {
    getMemoryCards: vi.fn(),
    renameMemoryCard: vi.fn(),
    setMemoryCardVisibility: vi.fn(),
  },
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => vi.fn(),
}));

const card = {
  id: 7,
  name: "Main",
  emulator: "pcsx2",
  is_public: false,
  updated_at: "2026-09-24T10:00:00Z",
} as MemoryCardSchema;

const RBtn = {
  props: { ariaLabel: { type: String, default: "" } },
  emits: ["click"],
  template: `<button :aria-label="ariaLabel" @click="$emit('click')"><slot /></button>`,
};
// Hands the parent whatever the test submits, standing in for the form.
const MemoryCardDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["submit"],
  template: `<div v-if="modelValue" class="edit-dialog" />`,
};

async function openEdit() {
  const wrapper = mount(MemoryCardManager, {
    props: { emulator: "pcsx2" },
    global: {
      stubs: { RBtn, MemoryCardDialog, PublicBadge: true, RIcon: true },
    },
  });
  await flushPromises();
  await wrapper.get('[aria-label="play.edit-memory-card"]').trigger("click");
  const dialog = wrapper
    .findAllComponents(MemoryCardDialog)
    .find((d) => d.props("modelValue"));
  return { wrapper, dialog: dialog! };
}

describe("MemoryCardManager edit", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(memoryCardApi.getMemoryCards).mockResolvedValue({
      data: [card],
    } as never);
    vi.mocked(memoryCardApi.renameMemoryCard).mockResolvedValue({
      data: { ...card, name: "Renamed" },
    } as never);
    vi.mocked(memoryCardApi.setMemoryCardVisibility).mockResolvedValue({
      data: { ...card, is_public: true },
    } as never);
  });

  it("only renames when only the name changed", async () => {
    const { dialog } = await openEdit();

    dialog.vm.$emit("submit", { name: "Renamed", isPublic: false });
    await flushPromises();

    expect(memoryCardApi.renameMemoryCard).toHaveBeenCalledWith({
      id: 7,
      name: "Renamed",
    });
    expect(memoryCardApi.setMemoryCardVisibility).not.toHaveBeenCalled();
  });

  it("only shares when only the visibility changed", async () => {
    const { wrapper, dialog } = await openEdit();

    dialog.vm.$emit("submit", { name: "Main", isPublic: true });
    await flushPromises();

    expect(memoryCardApi.renameMemoryCard).not.toHaveBeenCalled();
    expect(memoryCardApi.setMemoryCardVisibility).toHaveBeenCalledWith({
      id: 7,
      isPublic: true,
    });
    expect(wrapper.find(".edit-dialog").exists()).toBe(false);
  });
});
