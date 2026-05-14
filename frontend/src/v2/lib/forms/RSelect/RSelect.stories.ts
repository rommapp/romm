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

// ── Searchable ─────────────────────────────────────────────────────

export const Searchable: Story = {
  render: () => ({
    components: { RSelect },
    setup: () => {
      const value = ref<string | null>(null);
      const search = ref("");
      return { value, search, items: PLATFORMS };
    },
    template: `<div style="width:340px"><RSelect v-model="value" v-model:search="search" :items="items" searchable search-placeholder="Filter platforms" placeholder="Pick a platform" /></div>`,
  }),
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
