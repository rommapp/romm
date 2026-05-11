import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { computed, ref } from "vue";
import RMenuItem from "../RMenuItem/RMenuItem.vue";
import RMenuPanel from "../RMenuPanel/RMenuPanel.vue";
import RMenuSearch from "./RMenuSearch.vue";

const meta: Meta<typeof RMenuSearch> = {
  title: "Menus/RMenuSearch",
  component: RMenuSearch,
  argTypes: {
    placeholder: { control: "text" },
    autoFocus: { control: "boolean" },
  },
};

export default meta;
type Story = StoryObj<typeof RMenuSearch>;

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
];

export const Default: Story = {
  args: {
    placeholder: "Search platforms…",
    autoFocus: false,
  },
  render: (args) => ({
    components: { RMenuPanel, RMenuSearch, RMenuItem },
    setup() {
      const query = ref("");
      const filtered = computed(() =>
        PLATFORMS.filter((p) =>
          p.toLowerCase().includes(query.value.toLowerCase()),
        ),
      );
      return { args, query, filtered };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 40px; background: #07070f;">
        <RMenuPanel width="280px" max-height="260px">
          <RMenuSearch v-bind="args" v-model="query" />
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
