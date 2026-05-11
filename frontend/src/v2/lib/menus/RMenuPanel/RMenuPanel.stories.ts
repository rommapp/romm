import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { computed, ref } from "vue";
import RMenuDivider from "../RMenuDivider/RMenuDivider.vue";
import RMenuHeader from "../RMenuHeader/RMenuHeader.vue";
import RMenuItem from "../RMenuItem/RMenuItem.vue";
import RMenuPanel from "./RMenuPanel.vue";

const meta: Meta<typeof RMenuPanel> = {
  title: "Menus/RMenuPanel",
  component: RMenuPanel,
  argTypes: {
    width: { control: "text" },
    padding: { control: "text" },
  },
};

export default meta;

type Story = StoryObj<typeof RMenuPanel>;

export const Default: Story = {
  render: (args) => ({
    components: { RMenuPanel, RMenuHeader, RMenuItem, RMenuDivider },
    setup: () => ({ args }),
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 40px; background: #07070f;">
        <RMenuPanel v-bind="args">
          <RMenuHeader title="Super Mario World" subtitle="Super Nintendo">
            <template #art>
              <div style="width:38px;height:51px;border-radius:5px;background:#3f2a7c;" />
            </template>
          </RMenuHeader>
          <RMenuDivider />
          <RMenuItem label="Play" icon="mdi-play" />
          <RMenuItem label="Download" icon="mdi-download-outline" />
          <RMenuDivider />
          <RMenuItem label="Remove from favorites" icon="mdi-heart" variant="active" />
          <RMenuDivider />
          <RMenuItem label="Delete…" icon="mdi-trash-can-outline" variant="danger" />
        </RMenuPanel>
      </div>
    `,
  }),
};

const PLATFORMS = [
  "Nintendo 64",
  "Nintendo DS",
  "Nintendo Switch",
  "PlayStation",
  "PlayStation 2",
  "PlayStation Portable",
  "Sega Genesis",
  "Sega Saturn",
  "Super Nintendo",
  "Game Boy",
  "Game Boy Advance",
  "Game Boy Color",
  "Master System",
  "Arcade",
];

export const Searchable: Story = {
  render: () => ({
    components: { RMenuPanel, RMenuItem },
    setup() {
      const query = ref("");
      const filtered = computed(() =>
        PLATFORMS.filter((p) =>
          p.toLowerCase().includes(query.value.toLowerCase()),
        ),
      );
      return { query, filtered };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 40px; background: #07070f;">
        <RMenuPanel
          width="280px"
          max-height="280px"
          searchable
          v-model:search="query"
          search-placeholder="Search platforms…"
          :search-auto-focus="false"
        >
          <RMenuItem
            v-for="p in filtered"
            :key="p"
            :label="p"
            icon="mdi-controller"
          />
        </RMenuPanel>
      </div>
    `,
  }),
};
