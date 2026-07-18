import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, within } from "storybook/test";
import { ref } from "vue";
import RDropzone from "./RDropzone.vue";

const meta: Meta<typeof RDropzone> = {
  title: "Forms/RDropzone",
  component: RDropzone,
  argTypes: {
    title: { control: "text" },
    hint: { control: "text" },
    activeTitle: { control: "text" },
    releaseLabel: { control: "text" },
    icon: { control: "text" },
    activeIcon: { control: "text" },
    accept: { control: "text" },
    multiple: { control: "boolean" },
    disabled: { control: "boolean" },
    overlay: { control: "boolean" },
  },
  args: {
    title: "Drop files here",
    hint: "Drag and drop, or click to browse",
    activeTitle: "Release to upload",
    inputLabel: "Upload files",
    multiple: true,
  },
  render: (args) => ({
    components: { RDropzone },
    setup() {
      const picked = ref<string[]>([]);
      function onFiles(files: File[]) {
        picked.value = files.map((f) => f.name);
      }
      return { args, picked, onFiles };
    },
    template: `
      <div style="max-width: 520px">
        <RDropzone v-bind="args" @files="onFiles" />
        <p v-if="picked.length" style="margin-top: 12px; font-size: 12px">
          Picked: {{ picked.join(", ") }}
        </p>
      </div>
    `,
  }),
};

export default meta;
type Story = StoryObj<typeof RDropzone>;

// Default empty-state call-to-action.
export const CTA: Story = {};

export const Disabled: Story = {
  args: { disabled: true },
};

// Overlay mode wraps existing content; the drag-over overlay floats on top.
export const Overlay: Story = {
  args: { overlay: true, releaseLabel: "Release to upload" },
  render: (args) => ({
    components: { RDropzone },
    setup: () => ({ args }),
    template: `
      <div style="max-width: 520px">
        <RDropzone v-bind="args">
          <div
            style="
              display: grid;
              grid-template-columns: repeat(3, 1fr);
              gap: 8px;
            "
          >
            <div
              v-for="n in 6"
              :key="n"
              style="
                aspect-ratio: 16 / 9;
                border-radius: 6px;
                background: var(--r-color-cover-placeholder);
              "
            />
          </div>
        </RDropzone>
      </div>
    `,
  }),
};

// Interaction: the CTA renders its copy and is keyboard-focusable.
export const Interaction: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const button = canvas.getByRole("button");
    await expect(button).toBeInTheDocument();
    await expect(canvas.getByText("Drop files here")).toBeInTheDocument();
    button.focus();
    await expect(button).toHaveFocus();
  },
};
