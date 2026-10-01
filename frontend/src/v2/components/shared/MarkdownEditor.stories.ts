import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, waitFor } from "storybook/test";
import { ref } from "vue";
import MarkdownEditor from "@/v2/components/shared/MarkdownEditor.vue";

const meta: Meta<typeof MarkdownEditor> = {
  title: "Shared/MarkdownEditor",
  component: MarkdownEditor,
  render: () => ({
    components: { MarkdownEditor },
    setup: () => ({
      content: ref("# My note\n\nWrite **Markdown** here."),
    }),
    template: `<div style="max-width: 720px"><MarkdownEditor v-model="content" /></div>`,
  }),
};

export default meta;
type Story = StoryObj<typeof MarkdownEditor>;

export const Default: Story = {
  // md-editor's CodeMirror textbox has no accessible name (aria-input-field-name).
  // Naming it needs EditorView.contentAttributes via the loader's
  // codeMirrorExtensions config; tracked as a follow-up.
  parameters: { a11y: { test: "todo" } },
  play: async ({ canvasElement }) => {
    // The library loads on first render, then mounts its toolbar and editor.
    await waitFor(
      () =>
        expect(
          canvasElement.querySelector(".md-editor-toolbar"),
        ).not.toBeNull(),
      { timeout: 5000 },
    );
    await expect(canvasElement.textContent).toContain("My note");
  },
};
