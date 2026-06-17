import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import RIcon from "@/v2/lib/primitives/RIcon/RIcon.vue";
import RSelect from "./RSelect.vue";

const ROLES = [
  { title: "Admin", value: "admin" },
  { title: "Editor", value: "editor" },
  { title: "Viewer", value: "viewer" },
  { title: "Guest", value: "guest", disabled: true },
];

const PLATFORMS = [
  { title: "Nintendo 64", value: "n64" },
  { title: "Super Nintendo", value: "snes" },
  { title: "PlayStation 1", value: "psx" },
  { title: "PlayStation 2", value: "ps2" },
  { title: "Sega Genesis", value: "gen" },
  { title: "Game Boy", value: "gb" },
  { title: "Game Boy Advance", value: "gba" },
  { title: "Nintendo DS", value: "nds" },
  { title: "Nintendo Switch", value: "switch" },
  { title: "Xbox 360", value: "x360" },
  { title: "PC", value: "pc" },
];

const meta: Meta<typeof RSelect> = {
  title: "Forms/RSelect",
  component: RSelect,
  argTypes: {
    variant: {
      control: "inline-radio",
      options: ["outlined", "filled", "underlined", "plain"],
    },
    density: {
      control: "inline-radio",
      options: ["default", "comfortable", "compact"],
    },
    prefixLabel: {
      control: "inline-radio",
      options: [undefined, "stacked", "inline"],
    },
    label: { control: "text" },
    placeholder: { control: "text" },
    multiple: { control: "boolean" },
    chips: { control: "boolean" },
    closableChips: { control: "boolean" },
    chipTone: {
      control: "select",
      options: [
        "neutral",
        "brand",
        "accent",
        "success",
        "danger",
        "warning",
        "info",
        "plain",
      ],
    },
    clearable: { control: "boolean" },
    disabled: { control: "boolean" },
    readonly: { control: "boolean" },
    loading: { control: "boolean" },
    searchable: { control: "boolean" },
    error: { control: "boolean" },
    errorMessages: { control: "text" },
  },
  render: (args) => ({
    components: { RSelect },
    setup: () => {
      const value = ref<unknown>(args.multiple ? [] : null);
      return { args, value, items: PLATFORMS };
    },
    template: `
      <div style="width:340px">
        <RSelect v-model="value" :items="items" v-bind="args" />
      </div>
    `,
  }),
};

export default meta;

type Story = StoryObj<typeof RSelect>;

// ── Defaults ────────────────────────────────────────────────────────

export const Default: Story = {
  args: { placeholder: "Pick a platform" },
};

export const Preselected: Story = {
  render: () => ({
    components: { RSelect },
    setup: () => ({ value: ref("psx"), items: PLATFORMS }),
    template: `<div style="width:340px"><RSelect v-model="value" :items="items" placeholder="Pick a platform" /></div>`,
  }),
};

// ── Variants ────────────────────────────────────────────────────────

export const VariantLadder: Story = {
  name: "Variant ladder",
  render: () => ({
    components: { RSelect },
    setup: () => ({
      outlined: ref("psx"),
      filled: ref("psx"),
      underlined: ref("psx"),
      plain: ref("psx"),
      items: PLATFORMS,
    }),
    template: `
      <div style="display:flex;flex-direction:column;gap:16px;width:340px">
        <RSelect v-model="outlined" :items="items" variant="outlined" placeholder="outlined (default)" />
        <RSelect v-model="filled" :items="items" variant="filled" placeholder="filled" />
        <RSelect v-model="underlined" :items="items" variant="underlined" placeholder="underlined" />
        <RSelect v-model="plain" :items="items" variant="plain" placeholder="plain" />
      </div>
    `,
  }),
};

// ── Densities ──────────────────────────────────────────────────────

export const DensityLadder: Story = {
  name: "Density ladder",
  render: () => ({
    components: { RSelect },
    setup: () => ({
      a: ref(""),
      b: ref(""),
      c: ref(""),
      items: PLATFORMS,
    }),
    template: `
      <div style="display:flex;flex-direction:column;gap:14px;width:340px">
        <RSelect v-model="a" :items="items" density="default" placeholder="default · 48px" />
        <RSelect v-model="b" :items="items" density="comfortable" placeholder="comfortable · 40px" />
        <RSelect v-model="c" :items="items" density="compact" placeholder="compact · 32px" />
      </div>
    `,
  }),
};

// ── Labels ──────────────────────────────────────────────────────────

export const StackedLabel: Story = {
  name: "Label · stacked",
  args: {
    prefixLabel: "stacked",
    label: "Default platform",
    placeholder: "Pick one",
  },
};

export const InlineLabel: Story = {
  name: "Label · inline",
  args: {
    prefixLabel: "inline",
    label: "Platform",
    placeholder: "Pick one",
  },
};

// ── States ──────────────────────────────────────────────────────────

export const Disabled: Story = {
  args: {
    label: "Platform",
    prefixLabel: "stacked",
    disabled: true,
    placeholder: "Locked",
    modelValue: "psx",
  },
};

export const Loading: Story = {
  args: { placeholder: "Loading platforms…", loading: true },
};

export const WithError: Story = {
  args: {
    placeholder: "Pick a platform",
    error: true,
    errorMessages: "Required",
  },
};

export const Validation: Story = {
  name: "Rules · live validation",
  render: () => ({
    components: { RSelect },
    setup: () => {
      const value = ref<string | null>(null);
      const rules = [
        (v: unknown) => (v != null && v !== "" ? true : "Pick a platform"),
      ];
      return { value, rules, items: PLATFORMS };
    },
    template: `
      <div style="width:340px;display:flex;flex-direction:column;gap:8px">
        <RSelect v-model="value" :items="items" prefix-label="stacked" label="Platform" :rules="rules" placeholder="Pick one" />
        <div style="font:11px sans-serif;color:var(--r-color-fg-muted)">Open and close without picking — the error appears on blur.</div>
      </div>
    `,
  }),
};

// ── Clearable ──────────────────────────────────────────────────────

export const Clearable: Story = {
  render: () => ({
    components: { RSelect },
    setup: () => ({ value: ref("psx"), items: PLATFORMS }),
    template: `<div style="width:340px"><RSelect v-model="value" :items="items" placeholder="Clearable" clearable /></div>`,
  }),
};

// ── Multiple ───────────────────────────────────────────────────────

export const Multiple: Story = {
  name: "Multiple (chips)",
  render: () => ({
    components: { RSelect },
    setup: () => ({ value: ref(["psx", "snes"]), items: PLATFORMS }),
    template: `<div style="width:480px"><RSelect v-model="value" :items="items" multiple chips closable-chips placeholder="Pick platforms" /></div>`,
  }),
};

export const MultipleOverflow: Story = {
  name: "Multiple · dynamic overflow",
  render: () => ({
    components: { RSelect },
    setup: () => ({
      narrow: ref(["psx", "snes", "n64", "gba", "switch"]),
      wide: ref(["psx", "snes", "n64", "gba", "switch"]),
      items: PLATFORMS,
    }),
    template: `
      <div style="display:flex;flex-direction:column;gap:18px">
        <div style="width:240px">
          <RSelect v-model="narrow" :items="items" multiple chips closable-chips placeholder="Pick platforms" />
        </div>
        <div style="width:520px">
          <RSelect v-model="wide" :items="items" multiple chips closable-chips placeholder="Pick platforms" />
        </div>
        <div style="font:11px sans-serif;color:var(--r-color-fg-muted);max-width:520px">
          Same 5 selections, different activator widths — the narrow one collapses to "+N" sooner, the wide one fits more chips. Resize the Storybook frame to watch it recompute live.
        </div>
      </div>
    `,
  }),
};

// ── Searchable ─────────────────────────────────────────────────────

// `searchable` filters items internally without any v-model:search
// binding. Drop in the prop and the menu gets a search field that
// filters the list as you type. (Previously this required the parent
// to wire v-model:search to a ref + manually filter `items`.)
export const Searchable: Story = {
  render: () => ({
    components: { RSelect },
    setup: () => ({ value: ref<string | null>(null), items: PLATFORMS }),
    template: `<div style="width:340px"><RSelect v-model="value" :items="items" searchable search-placeholder="Filter platforms" placeholder="Pick a platform" /></div>`,
  }),
  parameters: {
    docs: {
      description: {
        story:
          "Internal search state — no `v-model:search` binding required. Parents that *do* want to react to the query can still bind `v-model:search` and it syncs both ways.",
      },
    },
  },
};

export const SearchableExternal: Story = {
  name: "Searchable · external v-model:search",
  render: () => ({
    components: { RSelect },
    setup: () => {
      const value = ref<string | null>(null);
      const search = ref("");
      return { value, search, items: PLATFORMS };
    },
    template: `
      <div style="width:340px;display:flex;flex-direction:column;gap:8px">
        <RSelect v-model="value" v-model:search="search" :items="items" searchable search-placeholder="Filter platforms" placeholder="Pick a platform" />
        <span style="font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">External query: <code>{{ search || '∅' }}</code></span>
      </div>
    `,
  }),
};

// ── Chip tone ──────────────────────────────────────────────────────

// `chipTone` controls how the selection chips render in multi mode.
// Default `brand` paints a brand-coloured pill; `plain` strips the
// pill background entirely (used by PlatformSelect to let icons read
// without surrounding colour); the rest pick a semantic tone.
export const ChipTones: Story = {
  name: "Chip tones (multiple)",
  render: () => ({
    components: { RSelect },
    setup: () => ({
      a: ref<string[]>(["psx", "snes"]),
      b: ref<string[]>(["psx", "snes"]),
      c: ref<string[]>(["psx", "snes"]),
      d: ref<string[]>(["psx", "snes"]),
      e: ref<string[]>(["psx", "snes"]),
      items: PLATFORMS,
    }),
    template: `
      <div style="display:flex;flex-direction:column;gap:12px;width:340px;font:11px/1.2 sans-serif;color:var(--r-color-fg-muted)">
        <div><span>brand (default)</span><RSelect v-model="a" :items="items" multiple chips chip-tone="brand" placeholder="Platforms" /></div>
        <div><span>plain (no fill)</span><RSelect v-model="b" :items="items" multiple chips chip-tone="plain" placeholder="Platforms" /></div>
        <div><span>neutral</span><RSelect v-model="c" :items="items" multiple chips chip-tone="neutral" placeholder="Platforms" /></div>
        <div><span>success</span><RSelect v-model="d" :items="items" multiple chips chip-tone="success" placeholder="Platforms" /></div>
        <div><span>danger</span><RSelect v-model="e" :items="items" multiple chips chip-tone="danger" placeholder="Platforms" /></div>
      </div>
    `,
  }),
  parameters: {
    docs: {
      description: {
        story:
          'Use `chip-tone="plain"` when chips carry their own visual weight (e.g. PlatformSelect\'s icon-only chips) and the pill background would be visual noise.',
      },
    },
  },
};

// ── Chip slot ──────────────────────────────────────────────────────

// Use the `#chip` slot to fully control chip content — replace the
// default label/title with a custom layout (icon, avatar, mini-card).
// The slot receives the active item; styling falls back to chipTone.
export const ChipSlotIconOnly: Story = {
  name: "#chip slot — icon-only chips",
  render: () => ({
    components: { RSelect, RIcon },
    setup: () => ({
      value: ref<string[]>(["psx", "snes", "n64"]),
      items: PLATFORMS,
    }),
    template: `
      <div style="width:340px">
        <RSelect v-model="value" :items="items" multiple chips chip-tone="plain" placeholder="Platforms">
          <template #chip="{ item }">
            <span style="display:inline-flex;align-items:center;gap:6px">
              <RIcon
                :icon="item.value === 'psx' ? 'mdi-playstation' : item.value === 'snes' ? 'mdi-nintendo-switch' : item.value === 'n64' ? 'mdi-nintendo-game-boy' : 'mdi-gamepad-square-outline'"
                size="x-small"
              />
              <span style="font-size:11px">{{ item.title }}</span>
            </span>
          </template>
        </RSelect>
      </div>
    `,
  }),
  parameters: {
    docs: {
      description: {
        story:
          "The `#chip` slot replaces only the chip content — chip-tone still controls the pill background. PlatformSelect uses this pattern to show platform icons (and only icons, with a tooltip) as compact chips.",
      },
    },
  },
};

// ── Custom slots ───────────────────────────────────────────────────

export const CustomSelectionSlot: Story = {
  name: "#selection slot — custom display",
  render: () => ({
    components: { RSelect, RIcon },
    setup: () => ({ value: ref("admin"), items: ROLES }),
    template: `
      <div style="width:340px">
        <RSelect v-model="value" :items="items" prefix-label="stacked" label="Role">
          <template #selection="{ item }">
            <span style="display:inline-flex;align-items:center;gap:6px">
              <RIcon :icon="item.value === 'admin' ? 'mdi-shield-crown' : item.value === 'editor' ? 'mdi-pencil' : item.value === 'viewer' ? 'mdi-eye' : 'mdi-account'" size="x-small" />
              {{ item.title }}
            </span>
          </template>
        </RSelect>
      </div>
    `,
  }),
};

export const CustomItemSlot: Story = {
  name: "#item slot — custom rows",
  render: () => ({
    components: { RSelect, RIcon },
    setup: () => ({ value: ref("editor"), items: ROLES }),
    template: `
      <div style="width:340px">
        <RSelect v-model="value" :items="items" prefix-label="stacked" label="Role">
          <template #item="{ item, props, selected, active }">
            <li v-bind="props" :style="{
              display:'flex',
              alignItems:'center',
              gap:'10px',
              padding:'9px 12px',
              borderRadius:'9px',
              marginBottom:'2px',
              cursor:'pointer',
              background: active || selected ? 'var(--r-color-surface)' : 'transparent',
              color: selected
                ? 'var(--r-color-brand-primary)'
                : active
                  ? 'var(--r-color-fg)'
                  : 'var(--r-color-fg-secondary)',
              transition: 'background var(--r-motion-fast) var(--r-motion-ease-out), color var(--r-motion-fast) var(--r-motion-ease-out)',
            }">
              <RIcon :icon="item.value === 'admin' ? 'mdi-shield-crown' : item.value === 'editor' ? 'mdi-pencil' : item.value === 'viewer' ? 'mdi-eye' : 'mdi-account'" size="x-small" />
              <span style="flex:1">{{ item.title }}</span>
              <RIcon v-if="selected" icon="mdi-check" size="x-small" />
            </li>
          </template>
        </RSelect>
      </div>
    `,
  }),
};

// ── Real-world ────────────────────────────────────────────────────

export const FormRow: Story = {
  name: "Form row (real-world)",
  render: () => ({
    components: { RSelect },
    setup: () => ({
      role: ref("editor"),
      platform: ref("psx"),
      roles: ROLES,
      platforms: PLATFORMS,
    }),
    template: `
      <div style="width:380px;display:flex;flex-direction:column;gap:14px;padding:20px;background:var(--r-color-bg-elevated);border:1px solid var(--r-color-border);border-radius:12px">
        <RSelect v-model="role" :items="roles" prefix-label="stacked" label="Role" />
        <RSelect v-model="platform" :items="platforms" prefix-label="stacked" label="Default platform" searchable />
      </div>
    `,
  }),
};
