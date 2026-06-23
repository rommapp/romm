import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { ref } from "vue";
import "./RAlert.stories.css";
import RAlert from "./RAlert.vue";

const meta: Meta<typeof RAlert> = {
  title: "Primitives/RAlert",
  component: RAlert,
  argTypes: {
    type: {
      control: "select",
      options: [undefined, "success", "info", "warning", "error"],
    },
    variant: {
      control: "select",
      options: ["flat", "elevated", "translucent", "outlined", "text"],
    },
    density: {
      control: "select",
      options: ["default", "comfortable", "compact"],
    },
    rounded: { control: "text" },
    closable: { control: "boolean" },
    title: { control: "text" },
    text: { control: "text" },
    icon: { control: "text" },
  },
  render: (args) => ({
    components: { RAlert },
    setup: () => ({ args }),
    template: `<div style="width:480px"><RAlert v-bind="args" /></div>`,
  }),
};

export default meta;

type Story = StoryObj<typeof RAlert>;

// ── Tones ───────────────────────────────────────────────────────────

export const Success: Story = {
  args: { type: "success", text: "Reset link sent to your email." },
};

export const Info: Story = {
  args: { type: "info", text: "Library scan is in progress." },
};

export const Warning: Story = {
  args: {
    type: "warning",
    title: "Hash calculation disabled",
    text: "ROMs will not be fingerprinted during this scan.",
  },
};

export const Error: Story = {
  args: { type: "error", text: "Unable to reach the server." },
};

export const AllTypes: Story = {
  name: "All types · translucent",
  render: () => ({
    components: { RAlert },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px;width:480px">
        <RAlert type="success" text="Reset link sent to your email." />
        <RAlert type="info" text="Library scan is in progress." />
        <RAlert type="warning" text="Hash calculation is disabled — ROMs won't be fingerprinted." />
        <RAlert type="error" text="Unable to reach the server." />
      </div>
    `,
  }),
};

// ── Variants ────────────────────────────────────────────────────────

export const Variants: Story = {
  name: "Variants · same type",
  render: () => ({
    components: { RAlert },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px;width:480px">
        <RAlert type="warning" variant="translucent" text="translucent — default · soft tint" />
        <RAlert type="warning" variant="flat" text="flat — solid colour fill, white text" />
        <RAlert type="warning" variant="elevated" text="elevated — flat + drop shadow" />
        <RAlert type="warning" variant="outlined" text="outlined — border only" />
        <RAlert type="warning" variant="text" text="text — no chrome, coloured text only" />
      </div>
    `,
  }),
};

// ── Density ────────────────────────────────────────────────────────

export const Density: Story = {
  name: "Density compression",
  render: () => ({
    components: { RAlert },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px;width:480px">
        <RAlert type="info" density="default" text="default — generous padding for prominent alerts" />
        <RAlert type="info" density="comfortable" text="comfortable — middle ground" />
        <RAlert type="info" density="compact" text="compact — inline form-validation feel" />
      </div>
    `,
  }),
};

// ── Title + body ────────────────────────────────────────────────────

export const TitleAndBody: Story = {
  name: "Title + body slot",
  render: () => ({
    components: { RAlert },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px;width:480px">
        <RAlert type="error">
          <template #title>Config file not mounted</template>
          The RomM container couldn't read its config file. Settings changes
          made here won't persist until the volume is mounted.
        </RAlert>
        <RAlert type="warning">
          <template #title>Config file not writable</template>
          The config file is mounted but read-only. Changes here will apply
          for this session only.
        </RAlert>
      </div>
    `,
  }),
};

// ── Icon ───────────────────────────────────────────────────────────

export const CustomIcon: Story = {
  name: "Icon override / suppress",
  render: () => ({
    components: { RAlert },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px;width:480px;font:12px/1.4 sans-serif;color:var(--r-color-fg-muted)">
        <RAlert type="info" text="Default — auto-picks mdi-information." />
        <RAlert type="info" icon="mdi-rocket-launch" text="Custom icon override." />
        <RAlert type="info" :icon="false" text="Icon suppressed — text-only banner." />
      </div>
    `,
  }),
};

export const PrependSlot: Story = {
  name: "Prepend slot (custom prepend)",
  render: () => ({
    components: { RAlert },
    template: `
      <RAlert type="info" density="compact" style="width:420px">
        <template #prepend>
          <div class="r-alert-story-spinner" />
        </template>
        Scanning Nintendo 64… 42 / 128 ROMs
      </RAlert>
    `,
  }),
};

// ── Closable ───────────────────────────────────────────────────────

export const Closable: Story = {
  name: "Closable (interactive)",
  render: () => ({
    components: { RAlert },
    setup() {
      const visible = ref(true);
      function reset() {
        visible.value = false;
        setTimeout(() => {
          visible.value = true;
        }, 250);
      }
      return { visible, reset };
    },
    template: `
      <div style="display:flex;flex-direction:column;gap:14px;width:480px;align-items:flex-start">
        <RAlert
          v-model="visible"
          type="success"
          title="Token created"
          text="Make sure to copy it now — you won't see it again."
          closable
        />
        <button
          type="button"
          style="padding:6px 12px;background:var(--r-color-brand-primary);color:white;border:none;border-radius:6px;font:12px/1 sans-serif;cursor:pointer"
          @click="reset"
        >
          Show again
        </button>
      </div>
    `,
  }),
};

// ── Real-world ──────────────────────────────────────────────────────

export const PatcherStatus: Story = {
  name: "Patcher status (real-world)",
  render: () => ({
    components: { RAlert },
    template: `
      <div style="display:flex;flex-direction:column;gap:12px;width:480px">
        <RAlert type="error" density="compact" text="Unable to load patch file: invalid format." />
        <RAlert type="info" density="compact" text="Applying patch — patience.xdelta to Game.bin" />
      </div>
    `,
  }),
};

export const FormValidation: Story = {
  name: "Form validation (inline)",
  render: () => ({
    components: { RAlert },
    template: `
      <div style="display:flex;flex-direction:column;gap:10px;width:380px;padding:18px;background:var(--r-color-bg-elevated);border-radius:12px">
        <input
          type="text"
          placeholder="New password"
          style="padding:8px 12px;background:var(--r-color-surface);border:1px solid var(--r-color-border);border-radius:6px;color:var(--r-color-fg);font:13px/1 sans-serif"
        />
        <input
          type="text"
          placeholder="Confirm password"
          style="padding:8px 12px;background:var(--r-color-surface);border:1px solid var(--r-color-danger);border-radius:6px;color:var(--r-color-fg);font:13px/1 sans-serif"
        />
        <RAlert type="error" density="compact" :icon="false" text="Passwords do not match" />
      </div>
    `,
  }),
};
