import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import type { SaveSchema, ScreenshotSchema } from "@/__generated__";
import AssetList from "./AssetList.vue";

// ── Mock builders ────────────────────────────────────────────────

const NOW = new Date("2026-05-25T20:00:00Z").getTime();
const HOUR = 3600 * 1000;

// 16:9 SVG stand-in for the screenshot a browser-player save carries.
function shot(hue: number): ScreenshotSchema {
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='64' height='36'><rect width='64' height='36' fill='hsl(${hue} 60% 40%)'/><rect x='8' y='8' width='48' height='20' fill='hsl(${hue} 70% 65%)'/></svg>`;
  return {
    download_path: `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`,
  } as ScreenshotSchema;
}

// One version in `slot`, `hoursAgo` old. Pass `slot: null` for an archive.
function makeSave(
  id: number,
  slot: string | null,
  hoursAgo: number,
  overrides: Partial<SaveSchema> = {},
): SaveSchema {
  const at = new Date(NOW - hoursAgo * HOUR).toISOString();
  // Slotted uploads carry the backend's datetime tag; archives keep their name.
  const stem = slot
    ? `chrono_trigger [${at.slice(0, 19).replace("T", "_").replace(/:/g, "-")}]`
    : `chrono_trigger_backup_${id}`;
  return {
    id,
    rom_id: 1,
    user_id: 1,
    file_name: `${stem}.srm`,
    file_name_no_tags: "chrono_trigger.srm",
    file_name_no_ext: stem,
    file_extension: "srm",
    file_path: "/saves/snes",
    file_size_bytes: 8 * 1024,
    full_path: `/saves/snes/${stem}.srm`,
    download_path: `/api/saves/${id}/content`,
    missing_from_fs: false,
    created_at: at,
    updated_at: at,
    emulator: "snes9x",
    slot,
    screenshot: null,
    ...overrides,
  } as SaveSchema;
}

// A slot with `count` versions from `firstId`, newest `hoursAgo` old.
function makeSlot(
  slot: string,
  count: number,
  hoursAgo: number,
  firstId: number,
): SaveSchema[] {
  return Array.from({ length: count }).map((_, i) =>
    makeSave(firstId + i, slot, hoursAgo + i * 26, {
      screenshot: shot((i * 47 + slot.length * 31) % 360),
    }),
  );
}

function library(): SaveSchema[] {
  return [
    ...makeSlot("autosave", 4, 1, 1),
    ...makeSlot("main_quest", 6, 30, 5),
    ...makeSlot("speedrun", 1, 200, 11),
    makeSave(12, null, 500),
    makeSave(13, null, 900, { emulator: null }),
  ];
}

const meta: Meta<typeof AssetList> = {
  title: "Shared/AssetList",
  component: AssetList,
  decorators: [
    () => ({
      template: `
        <div style="
          max-width: 520px;
          padding: 18px;
          background: var(--r-color-bg-elevated);
          border: 1px solid var(--r-color-border);
          border-radius: var(--r-radius-lg);
        ">
          <story />
        </div>
      `,
    }),
  ],
};

export default meta;
type Story = StoryObj<typeof AssetList>;

function selectable(saves: SaveSchema[], selected: number | null) {
  return {
    components: { AssetList },
    setup() {
      const selectedId = ref<number | null>(selected);
      return {
        saves,
        selectedId,
        onSelect: (a: SaveSchema) => (selectedId.value = a.id),
      };
    },
    template: `
      <AssetList :assets="saves" type="save" :selected-id="selectedId" @select="onSelect" />
    `,
  };
}

// ── Stories ──────────────────────────────────────────────────────

// Autosave history, two named slots and two archives: the full slot model.
export const SlotLibrary: Story = {
  name: "Slots · autosave, named, archive",
  render: () => {
    const saves = library();
    return selectable(saves, saves[0].id);
  },
};

// Selecting an older version unfolds its slot so the pick stays visible.
export const OlderVersionSelected: Story = {
  name: "Older version selected",
  render: () => {
    const saves = library();
    const olderMainQuest = saves.filter((s) => s.slot === "main_quest")[3];
    return selectable(saves, olderMainQuest.id);
  },
};

// Only manual uploads, no screenshots: the pre-slot shape of a library.
export const ArchiveOnly: Story = {
  name: "Archive only (no slots)",
  render: () => {
    const saves = [
      makeSave(1, null, 3),
      makeSave(2, null, 50, {
        file_name:
          "the_legend_of_zelda_a_link_to_the_past_speedrun_attempt_27.srm",
      }),
      makeSave(3, null, 400, { emulator: null }),
    ];
    return selectable(saves, null);
  },
};

// One slot, one version, the most common case for new players.
export const SingleSave: Story = {
  name: "Single save",
  render: () => {
    const saves = makeSlot("autosave", 1, 2, 1);
    return selectable(saves, saves[0].id);
  },
};

// Management mode: static rows hosting the actions slot.
export const Manage: Story = {
  name: "Manage (actions slot)",
  render: () => ({
    components: { AssetList },
    setup() {
      return { saves: library() };
    },
    template: `
      <AssetList :assets="saves" type="save" :selectable="false" :scrollable="false">
        <template #actions="{ asset }">
          <span style="font-size: 10px; color: var(--r-color-fg-muted)">#{{ asset.id }}</span>
        </template>
      </AssetList>
    `,
  }),
};

// Empty — distinct from "no save selected".
export const Empty: Story = {
  name: "Empty (no saves)",
  render: () => ({
    components: { AssetList },
    template: `
      <AssetList :assets="[]" type="save" :selected-id="null" />
    `,
  }),
};
