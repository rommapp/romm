import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { ref } from "vue";
import RBtn from "@/v2/lib/primitives/RBtn/RBtn.vue";
import REmptyState from "@/v2/lib/primitives/REmptyState/REmptyState.vue";
import RProgressCircular from "@/v2/lib/primitives/RProgressCircular/RProgressCircular.vue";
import RDialog from "./RDialog.vue";

const meta: Meta<typeof RDialog> = {
  title: "Overlays/RDialog",
  component: RDialog,
  argTypes: {
    icon: { control: "text" },
    width: { control: "text" },
    height: { control: "text" },
    scrollContent: { control: "boolean" },
    persistent: { control: "boolean" },
    fullscreenOnMobile: { control: "boolean" },
    bodyPadding: {
      control: "inline-radio",
      options: ["default", "compact", "flush"],
    },
  },
};

export default meta;

type Story = StoryObj<typeof RDialog>;

export const Basic: Story = {
  args: { width: "420", icon: "mdi-information" },
  render: (args) => ({
    components: { RDialog, RBtn },
    setup() {
      const open = ref(false);
      return { args, open };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 48px; background: #07070f; min-height: 300px;">
        <RBtn @click="open = true">Open dialog</RBtn>
        <RDialog v-bind="args" v-model="open">
          <template #header>
            <span>Dialog title</span>
          </template>
          <template #content>
            <p>This is the dialog body. Keep content concise and actionable.</p>
          </template>
          <template #footer-start>
            <RBtn variant="outlined" @click="open = false">Cancel</RBtn>
          </template>
          <template #footer>
            <RBtn color="primary" @click="open = false">Confirm</RBtn>
          </template>
        </RDialog>
      </div>
    `,
  }),
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);
    // The dialog teleports to <body>, outside the story canvas.
    const body = within(document.body);

    await step("Cancel sits left of the spacer, Confirm right", async () => {
      await userEvent.click(
        canvas.getByRole("button", { name: "Open dialog" }),
      );
      const dialog = await body.findByRole("dialog");
      const footer = dialog.querySelector(".r-dialog__footer");
      const items = Array.from(footer?.children ?? []).map((el) =>
        el.getAttribute("aria-hidden") === "true"
          ? "spacer"
          : el.textContent?.trim(),
      );
      expect(items).toEqual(["Cancel", "spacer", "Confirm"]);
    });

    await step("Cancel closes the dialog", async () => {
      await userEvent.click(body.getByRole("button", { name: "Cancel" }));
      await waitFor(() => expect(body.queryByRole("dialog")).toBeNull());
    });
  },
};

// Loading and empty states aren't built into the primitive any more —
// the consumer renders them inside `#content` from REmptyState /
// RProgressCircular. These stories demonstrate the recipe.
export const Loading: Story = {
  name: "Loading (composed)",
  args: { width: "420", height: "240", icon: "mdi-loading" },
  render: (args) => ({
    components: { RDialog, RBtn, RProgressCircular },
    setup() {
      const open = ref(false);
      return { args, open };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 48px; background: #07070f; min-height: 300px;">
        <RBtn @click="open = true">Open loading dialog</RBtn>
        <RDialog v-bind="args" v-model="open">
          <template #header>
            <span>Fetching…</span>
          </template>
          <template #content>
            <div style="flex:1;display:flex;align-items:center;justify-content:center;min-height:140px">
              <RProgressCircular indeterminate :size="40" />
            </div>
          </template>
        </RDialog>
      </div>
    `,
  }),
};

export const EmptyState: Story = {
  name: "Empty state (composed)",
  args: { width: "420", height: "320", icon: "mdi-search-web" },
  render: (args) => ({
    components: { RDialog, RBtn, REmptyState },
    setup() {
      const open = ref(false);
      return { args, open };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 48px; background: #07070f; min-height: 300px;">
        <RBtn @click="open = true">Open empty dialog</RBtn>
        <RDialog v-bind="args" v-model="open">
          <template #header>
            <span>Match metadata</span>
          </template>
          <template #content>
            <REmptyState
              icon="mdi-disc-alert"
              title="No results"
              hint="The game you were looking for doesn't match any provider."
              style="flex:1"
            />
          </template>
        </RDialog>
      </div>
    `,
  }),
};

export const WithToolbarAndFooter: Story = {
  args: { width: "520", icon: "mdi-pencil" },
  render: (args) => ({
    components: { RDialog, RBtn },
    setup() {
      const open = ref(false);
      return { args, open };
    },
    template: `
      <div class="r-v2 r-v2-dark" style="padding: 48px; background: #07070f; min-height: 300px;">
        <RBtn @click="open = true">Open full dialog</RBtn>
        <RDialog v-bind="args" v-model="open">
          <template #header><span>Edit ROM</span></template>
          <template #toolbar>
            <small style="color: rgba(255,255,255,0.55)">Super Mario World · Super Nintendo</small>
          </template>
          <template #content>
            <p>Body content with form fields would go here.</p>
          </template>
          <template #footer-start>
            <RBtn variant="outlined" @click="open = false">Cancel</RBtn>
          </template>
          <template #footer>
            <RBtn color="primary" @click="open = false">Save</RBtn>
          </template>
        </RDialog>
      </div>
    `,
  }),
};
