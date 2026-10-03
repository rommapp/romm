// The EmulatorJS pre-game "Resume" panel (tab switcher, AssetPreview and the
// save list or state strip), composed the way the player view renders it.
import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { RCard, RSliderBtnGroup } from "@v2/lib";
import type { SliderBtnGroupItem } from "@v2/lib/primitives/RSliderBtnGroup/types";
import { computed, ref } from "vue";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { makeSave, manyStates } from "@/v2/utils/saveStates.fixtures";
import AssetList from "../shared/AssetList.vue";
import AssetStrip from "../shared/AssetStrip.vue";
import AssetPreview from "./AssetPreview.vue";

const saveSlots = [
  "main_quest",
  "side_quest",
  "speedrun_attempt",
  "boss_rush",
  "casual_run",
];

function slotSaves(count: number): SaveSchema[] {
  return Array.from({ length: count }).map((_, i) =>
    makeSave(i + 1, saveSlots[i % saveSlots.length]!, (i + 1) * 4, {
      emulator: i % 2 === 0 ? "snes9x" : null,
    }),
  );
}

type AssetTab = "save" | "state";

interface Args {
  saves: SaveSchema[];
  states: StateSchema[];
  initialTab: AssetTab;
}

const meta: Meta<Args> = {
  title: "Player/ResumePanel (composition)",
  decorators: [
    () => ({
      template: `
        <div style="
          max-width: 720px;
          margin: 0 auto;
          padding: 24px;
        ">
          <story />
        </div>
      `,
    }),
  ],
};

export default meta;

type Story = StoryObj<Args>;

// Mirrors the structure inside `EmulatorJS.vue`.
function renderPanel(
  saves: SaveSchema[],
  states: StateSchema[],
  tab: AssetTab,
  selectFirst = true,
) {
  return {
    components: { AssetList, AssetPreview, AssetStrip, RCard, RSliderBtnGroup },
    setup() {
      const activeTab = ref<AssetTab>(tab);
      const first = (list: { id: number }[]) =>
        selectFirst ? (list[0]?.id ?? null) : null;
      const selectedSaveId = ref<number | null>(first(saves));
      const selectedStateId = ref<number | null>(first(states));

      const tabs = computed<SliderBtnGroupItem<AssetTab>[]>(() => [
        {
          id: "save",
          label: `Saves${saves.length ? ` · ${saves.length}` : ""}`,
          icon: "mdi-content-save",
        },
        {
          id: "state",
          label: `States${states.length ? ` · ${states.length}` : ""}`,
          icon: "mdi-file",
        },
      ]);

      const activeAssets = computed(() =>
        activeTab.value === "save" ? saves : states,
      );
      const selectedId = computed(() =>
        activeTab.value === "save"
          ? selectedSaveId.value
          : selectedStateId.value,
      );
      const selectedAsset = computed(() => {
        const list = activeAssets.value;
        const id = selectedId.value;
        return list.find((a) => a.id === id) ?? null;
      });
      const stripLabel = computed(() =>
        activeTab.value === "save" ? "All saves" : "All states",
      );

      function pick(a: SaveSchema | StateSchema) {
        if (activeTab.value === "save") {
          selectedSaveId.value = a.id;
          selectedStateId.value = null;
        } else {
          selectedStateId.value = a.id;
          selectedSaveId.value = null;
        }
      }
      function clear() {
        if (activeTab.value === "save") selectedSaveId.value = null;
        else selectedStateId.value = null;
      }
      function setTab(t: AssetTab) {
        activeTab.value = t;
      }

      return {
        activeTab,
        tabs,
        activeAssets,
        selectedId,
        selectedAsset,
        stripLabel,
        pick,
        clear,
        setTab,
      };
    },
    template: `
      <RCard
        variant="flat"
        style="
          background: var(--r-color-bg-elevated);
          border: 1px solid var(--r-color-border);
          border-radius: var(--r-radius-lg);
          backdrop-filter: blur(18px);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          min-height: 420px;
        "
      >
        <div style="padding:14px 14px 0;display:flex;justify-content:center">
          <RSliderBtnGroup
            variant="tab"
            :model-value="activeTab"
            :items="tabs"
            aria-label="Load save or state"
            @update:model-value="setTab"
          />
        </div>
        <div style="padding:14px;display:flex;flex-direction:column;gap:14px;flex:1">
          <AssetPreview :asset="selectedAsset" :type="activeTab" @clear="clear" />
          <div
            style="
              display:flex;
              align-items:center;
              gap:6px;
              font-size:10px;
              font-weight:600;
              text-transform:uppercase;
              letter-spacing:0.08em;
              color:var(--r-color-fg-secondary);
              margin-top:4px;
            "
          >
            <span>{{ stripLabel }}</span>
            <span
              style="
                display:inline-grid;
                place-items:center;
                min-width:18px;
                height:18px;
                padding:0 5px;
                background:var(--r-color-surface);
                border-radius:var(--r-radius-pill);
                font-size:10px;
                color:var(--r-color-fg-secondary);
              "
            >{{ activeAssets.length }}</span>
          </div>
          <AssetList
            v-if="activeTab === 'save'"
            :assets="activeAssets"
            type="save"
            :selected-id="selectedId"
            @select="pick"
          />
          <AssetStrip
            v-else
            :assets="activeAssets"
            type="state"
            :selected-id="selectedId"
            @select="pick"
          />
        </div>
      </RCard>
    `,
  };
}

// 8 states and 3 saves, the rich case. The state tab opens by default.
export const RichLibrary: Story = {
  name: "Rich · 8 states + 3 saves",
  render: () => renderPanel(slotSaves(3), manyStates(8), "state"),
};

// 15 states overflow the strip, which scrolls horizontally.
export const ManyStates: Story = {
  name: "Many states · 15 (overflow)",
  render: () => renderPanel([], manyStates(15), "state"),
};

export const MixedScreenshots: Story = {
  name: "States · mixed (with + without screenshots)",
  render: () => {
    const states = manyStates(6).map((s, i) =>
      i % 2 === 0 ? s : { ...s, screenshot: null },
    );
    return renderPanel([], states, "state");
  },
};

// Three save slots and no states yet.
export const SavesOnly: Story = {
  name: "Saves only · 3 slots",
  render: () => renderPanel(slotSaves(3), [], "save"),
};

export const SingleSave: Story = {
  name: "Single save",
  render: () => renderPanel(slotSaves(1), [], "save"),
};

// First launch: no saves, no states.
export const FreshGame: Story = {
  name: "Fresh game · no saves, no states",
  render: () => renderPanel([], [], "state"),
};

// The state tab after a core swap left no compatible states.
export const StatesEmptyAfterCoreChange: Story = {
  name: "States · empty after core swap",
  render: () => renderPanel(slotSaves(4), [], "state"),
};

export const NoneSelectedManyAvailable: Story = {
  name: "Many states · none selected",
  render: () => renderPanel([], manyStates(6), "state", false),
};
