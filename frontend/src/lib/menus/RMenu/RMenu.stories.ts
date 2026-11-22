import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { ref } from "vue";
import RMenuItem from "@/lib/menus/RMenuItem/RMenuItem.vue";
import RAvatar from "@/lib/primitives/RAvatar/RAvatar.vue";
import RBtn from "@/lib/primitives/RBtn/RBtn.vue";
import RDivider from "@/lib/primitives/RDivider/RDivider.vue";
import RIcon from "@/lib/primitives/RIcon/RIcon.vue";
import RMenu from "./RMenu.vue";

const meta: Meta<typeof RMenu> = {
  title: "Menus/RMenu",
  component: RMenu,
  argTypes: {
    location: {
      control: "inline-radio",
      options: [
        "top",
        "bottom",
        "start",
        "end",
        "top start",
        "top end",
        "bottom start",
        "bottom end",
      ],
    },
    width: { control: "text" },
    maxHeight: { control: "text" },
  },
};

export default meta;
type Story = StoryObj<typeof RMenu>;

// ── Defaults ──────────────────────────────────────────────────────

export const Basic: Story = {
  render: (args) => ({
    components: { RMenu, RMenuItem, RBtn },
    setup: () => ({ args }),
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <RMenu v-bind="args">
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="translucent" append-icon="mdi-chevron-down">
              Open menu
            </RBtn>
          </template>
          <RMenuItem icon="mdi-play" label="Play" />
          <RMenuItem icon="mdi-download-outline" label="Download" />
          <RMenuItem icon="mdi-pencil-outline" label="Edit" />
        </RMenu>
      </div>
    `,
  }),
};

// ── Keyboard: focus returns to the activator ──────────────────────

export const KeyboardFocusReturn: Story = {
  name: "Keyboard focus return (play)",
  globals: { input: "key" },
  render: () => ({
    components: { RMenu, RMenuItem, RBtn },
    setup: () => ({ picked: ref<string | null>(null) }),
    template: `
      <div style="padding:48px;display:flex;flex-direction:column;align-items:center;gap:12px">
        <RMenu>
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="translucent" append-icon="mdi-chevron-down">
              Sort by
            </RBtn>
          </template>
          <RMenuItem icon="mdi-sort-alphabetical-ascending" label="Name" @click="picked = 'Name'" />
          <RMenuItem icon="mdi-calendar" label="Release date" @click="picked = 'Release date'" />
          <RMenuItem icon="mdi-star-outline" label="Rating" @click="picked = 'Rating'" />
        </RMenu>
        <span data-testid="picked">{{ picked ?? "None" }}</span>
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    const activator = await canvas.findByRole("button", { name: /Sort by/ });
    const menu = () => document.querySelector('[role="menu"]');

    async function openFromKeyboard() {
      activator.focus();
      await userEvent.keyboard("{Enter}");
      await waitFor(() =>
        expect(document.activeElement).toHaveAccessibleName("Name"),
      );
    }

    await step("Enter opens the menu on the first item", openFromKeyboard);

    await step("Picking an item returns focus to the activator", async () => {
      await userEvent.keyboard("{ArrowDown}");
      await expect(document.activeElement).toHaveAccessibleName("Release date");
      await userEvent.keyboard("{Enter}");
      await waitFor(() => expect(menu()).toBeNull());
      await expect(canvas.getByTestId("picked")).toHaveTextContent(
        "Release date",
      );
      await expect(activator).toHaveFocus();
      await expect(activator).toHaveAttribute("aria-expanded", "false");
    });

    await step("Escape returns focus to the activator", async () => {
      await openFromKeyboard();
      await userEvent.keyboard("{Escape}");
      await waitFor(() => expect(menu()).toBeNull());
      await expect(activator).toHaveFocus();
    });
  },
};

// ── Account menu (real-world) ─────────────────────────────────────

export const AccountMenu: Story = {
  name: "Account menu (real-world)",
  render: () => ({
    components: { RMenu, RMenuItem, RBtn, RDivider, RAvatar },
    template: `
      <div style="padding:48px;display:flex;justify-content:flex-end">
        <RMenu location="bottom end" :offset="8" width="240px">
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="translucent" append-icon="mdi-chevron-down">
              <RAvatar size="22" />
              <span style="margin-left:6px">Jane</span>
            </RBtn>
          </template>

          <div style="display:flex;gap:10px;align-items:center;padding:10px 10px 12px">
            <RAvatar size="30" />
            <div style="min-width:0">
              <div style="font:600 13px/1.3 sans-serif">Jane Doe</div>
              <div style="font:600 10.5px/1.3 sans-serif;color:var(--r-color-fg-muted);text-transform:capitalize">Admin</div>
            </div>
          </div>

          <RDivider />

          <RMenuItem icon="mdi-account-outline" label="Profile" />
          <RMenuItem icon="mdi-palette-outline" label="Appearance" />
          <RMenuItem icon="mdi-cog-outline" label="Settings" />

          <RDivider />

          <RMenuItem icon="mdi-logout" variant="danger" label="Log out" />
        </RMenu>
      </div>
    `,
  }),
};

// ── Placements ────────────────────────────────────────────────────

export const Placements: Story = {
  name: "Placement ladder",
  render: () => ({
    components: { RMenu, RMenuItem, RBtn },
    template: `
      <div style="padding:80px;display:grid;grid-template-columns:repeat(4,auto);gap:24px;justify-content:center">
        <RMenu v-for="loc in ['top','bottom','start','end','top start','top end','bottom start','bottom end']" :key="loc" :location="loc">
          <template #activator="{ props }">
            <RBtn v-bind="props" size="small">{{ loc }}</RBtn>
          </template>
          <RMenuItem icon="mdi-arrow-up-right" label="One" />
          <RMenuItem icon="mdi-arrow-up-right" label="Two" />
          <RMenuItem icon="mdi-arrow-up-right" label="Three" />
        </RMenu>
      </div>
    `,
  }),
};

// ── Searchable ────────────────────────────────────────────────────

const PLATFORMS = [
  { slug: "n64", name: "Nintendo 64" },
  { slug: "snes", name: "Super Nintendo" },
  { slug: "psx", name: "PlayStation 1" },
  { slug: "ps2", name: "PlayStation 2" },
  { slug: "gen", name: "Sega Genesis" },
  { slug: "gb", name: "Game Boy" },
  { slug: "gba", name: "Game Boy Advance" },
  { slug: "nds", name: "Nintendo DS" },
  { slug: "switch", name: "Nintendo Switch" },
];

export const Searchable: Story = {
  name: "Searchable + filter",
  render: () => ({
    components: { RMenu, RMenuItem, RBtn },
    setup() {
      const query = ref("");
      const filtered = ref(PLATFORMS);
      function onSearch(q: string) {
        query.value = q;
        const lc = q.trim().toLowerCase();
        filtered.value = lc
          ? PLATFORMS.filter((p) => p.name.toLowerCase().includes(lc))
          : PLATFORMS;
      }
      return { query, filtered, onSearch };
    },
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <RMenu
          :search="query"
          searchable
          search-placeholder="Filter platforms"
          width="260px"
          max-height="320px"
          :close-on-content-click="false"
          @update:search="onSearch"
        >
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="translucent" prepend-icon="mdi-gamepad-variant">
              Pick a platform
            </RBtn>
          </template>
          <RMenuItem
            v-for="p in filtered"
            :key="p.slug"
            icon="mdi-gamepad-variant"
            :label="p.name"
          />
          <div v-if="!filtered.length" style="padding:12px;font:12px sans-serif;color:var(--r-color-fg-muted);text-align:center">
            No matches.
          </div>
        </RMenu>
      </div>
    `,
  }),
};

// ── Scroll on overflow ────────────────────────────────────────────

export const ScrollableMaxHeight: Story = {
  name: "Scrollable (maxHeight)",
  render: () => ({
    components: { RMenu, RMenuItem, RBtn },
    setup: () => ({
      items: Array.from({ length: 30 }, (_, i) => `Item ${i + 1}`),
    }),
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <RMenu width="220px" max-height="240px">
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="translucent">Long list</RBtn>
          </template>
          <RMenuItem v-for="(label, i) in items" :key="i" :label="label" icon="mdi-circle-small" />
        </RMenu>
      </div>
    `,
  }),
};

// ── Sticky menu (close-on-content-click false) ────────────────────

export const StickyMenu: Story = {
  name: "Sticky (close-on-content-click false)",
  render: () => ({
    components: { RMenu, RMenuItem, RBtn, RDivider },
    setup() {
      const toggles = ref({ sound: true, music: false, vibration: true });
      function flip(k: keyof typeof toggles.value) {
        toggles.value[k] = !toggles.value[k];
      }
      return { toggles, flip };
    },
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <RMenu width="220px" :close-on-content-click="false">
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="translucent" prepend-icon="mdi-tune-variant">
              Options
            </RBtn>
          </template>
          <RMenuItem
            :icon="toggles.sound ? 'mdi-volume-high' : 'mdi-volume-off'"
            label="Sound"
            :variant="toggles.sound ? 'active' : 'default'"
            @click="flip('sound')"
          />
          <RMenuItem
            :icon="toggles.music ? 'mdi-music' : 'mdi-music-off'"
            label="Music"
            :variant="toggles.music ? 'active' : 'default'"
            @click="flip('music')"
          />
          <RMenuItem
            :icon="toggles.vibration ? 'mdi-vibrate' : 'mdi-vibrate-off'"
            label="Vibration"
            :variant="toggles.vibration ? 'active' : 'default'"
            @click="flip('vibration')"
          />
          <RDivider />
          <RMenuItem icon="mdi-keyboard-close" label="Close menu" />
        </RMenu>
      </div>
    `,
  }),
};

// ── Open-on-hover ─────────────────────────────────────────────────

export const OpenOnHover: Story = {
  name: "Open on hover",
  render: () => ({
    components: { RMenu, RMenuItem, RBtn },
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <RMenu open-on-hover>
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="text">File</RBtn>
          </template>
          <RMenuItem icon="mdi-file-plus" label="New" />
          <RMenuItem icon="mdi-folder-open-outline" label="Open…" />
          <RMenuItem icon="mdi-content-save-outline" label="Save" />
        </RMenu>
      </div>
    `,
  }),
};

// ── Disabled activator ────────────────────────────────────────────

export const Disabled: Story = {
  args: { disabled: true },
  render: (args) => ({
    components: { RMenu, RMenuItem, RBtn },
    setup: () => ({ args }),
    template: `
      <div style="padding:48px;display:flex;justify-content:center">
        <RMenu v-bind="args">
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="translucent" disabled>Locked</RBtn>
          </template>
          <RMenuItem icon="mdi-circle" label="Never opens" />
        </RMenu>
      </div>
    `,
  }),
};

// ── Controlled open ───────────────────────────────────────────────

export const Controlled: Story = {
  name: "Controlled (v-model)",
  render: () => ({
    components: { RMenu, RMenuItem, RBtn, RIcon },
    setup: () => ({ open: ref(false) }),
    template: `
      <div style="padding:48px;display:flex;flex-direction:column;align-items:center;gap:12px">
        <RMenu v-model="open">
          <template #activator="{ props }">
            <RBtn v-bind="props" variant="translucent">Click target</RBtn>
          </template>
          <RMenuItem icon="mdi-information-outline" label="Hello" />
        </RMenu>
        <RBtn size="small" variant="text" @click="open = !open">
          <RIcon :icon="open ? 'mdi-eye-off' : 'mdi-eye'" size="14" />
          <span style="margin-left:6px">{{ open ? 'Force-close' : 'Force-open' }}</span>
        </RBtn>
      </div>
    `,
  }),
};
