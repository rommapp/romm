import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, waitFor } from "storybook/test";
import { MD_EDITOR_LOADER } from "@/plugins/mdeditor";
import MarkdownPreview from "@/v2/components/shared/MarkdownPreview.vue";

const SAMPLE = `# Chrono Trigger

A **time-travel** RPG. Notes support the usual Markdown:

- Lists, with \`inline code\`
- [Links](https://example.com)
- Tables

| Era | Year |
| --- | ---- |
| Present | 1000 AD |
| Future | 2300 AD |

\`\`\`
Save before the Black Omen.
\`\`\`

> Quotes render too.
`;

const LONG = Array.from(
  { length: 12 },
  (_, i) =>
    `## Chapter ${i + 1}\n\nWalkthrough text for chapter ${i + 1}, long enough to wrap across the preview width on a desktop viewport.\n`,
).join("\n");

const meta: Meta<typeof MarkdownPreview> = {
  title: "Shared/MarkdownPreview",
  component: MarkdownPreview,
  args: { modelValue: SAMPLE },
  argTypes: { modelValue: { control: "text" } },
  // Padded, not centered: a centered story shrinks to its content's width.
  parameters: { layout: "padded" },
  render: (args) => ({
    components: { MarkdownPreview },
    setup: () => ({ args }),
    template: `<div style="max-width: 720px"><MarkdownPreview v-bind="args" /></div>`,
  }),
};

export default meta;
type Story = StoryObj<typeof MarkdownPreview>;

export const Default: Story = {
  play: async ({ canvasElement }) => {
    // The library loads on first render, so wait for the rendered heading.
    await waitFor(() =>
      expect(
        canvasElement.querySelector(".md-editor-preview h1"),
      ).not.toBeNull(),
    );
  },
};

// Notes and release notes embed raw HTML; the loader's XSS config keeps the
// markup and strips anything executable.
export const RawHtml: Story = {
  args: {
    modelValue:
      'Line one<br>line two\n\n<img src="/assets/default/cover/big_dark_missing_cover.png" alt="Cover" onerror="alert(1)">\n\n<script>alert(2)</script>',
  },
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(
        canvasElement.querySelector(".md-editor-preview img"),
      ).not.toBeNull(),
    );
    const img = canvasElement.querySelector(".md-editor-preview img");
    await expect(img?.hasAttribute("onerror")).toBe(false);
    await expect(canvasElement.querySelector("script")).toBeNull();
  },
};

export const LongDocument: Story = {
  args: { modelValue: LONG },
};

// Shows the skeleton placeholder while the md-editor chunk is loading.
export const Loading: Story = {
  decorators: [
    (story) => ({
      components: { story },
      provide: { [MD_EDITOR_LOADER as symbol]: () => new Promise(() => {}) },
      template: "<story />",
    }),
  ],
  play: async ({ canvasElement }) => {
    // The skeleton renders immediately (after the 200ms delay built into
    // defineAsyncComponent); the real preview never appears.
    await waitFor(() =>
      expect(canvasElement.querySelector(".r-skeleton")).not.toBeNull(),
    );
    await expect(canvasElement.querySelector(".md-editor-preview")).toBeNull();
  },
};
