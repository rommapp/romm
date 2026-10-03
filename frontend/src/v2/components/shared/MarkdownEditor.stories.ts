import type { Meta, StoryObj } from "@storybook/vue3-vite";
import { expect, waitFor } from "storybook/test";
import { getCurrentInstance, ref } from "vue";
import MarkdownEditor from "@/v2/components/shared/MarkdownEditor.vue";
import { MD_LOADERS } from "@/v2/composables/useLazyMarkdown";

const meta: Meta<typeof MarkdownEditor> = {
  title: "Shared/MarkdownEditor",
  component: MarkdownEditor,
  parameters: { layout: "padded" },
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
    // The module loads on first render, then mounts its toolbar and editor.
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

// Shows the skeleton placeholder while the md-editor chunk is loading.
export const Loading: Story = {
  decorators: [
    (story) => ({
      components: { story },
      provide: {
        [MD_LOADERS as symbol]: { editor: () => new Promise(() => {}) },
      },
      template: "<story />",
    }),
  ],
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(canvasElement.querySelector(".r-skeleton")).not.toBeNull(),
    );
    await expect(canvasElement.querySelector(".md-editor-toolbar")).toBeNull();
  },
};

// The first load fails; click Try again to load the real chunk.
export const Failed: Story = {
  // Same unnamed CodeMirror textbox as Default, once Try again mounts the editor.
  parameters: { a11y: { test: "todo" } },
  decorators: [
    (story) => {
      let attempts = 0;
      return {
        components: { story },
        provide: {
          [MD_LOADERS as symbol]: {
            editor: () =>
              attempts++ === 0
                ? Promise.reject(new Error("chunk failed"))
                : import("@/v2/components/shared/markdownEditor"),
          },
        },
        setup() {
          // Vue reports a failed async load to the app handler, which would fail the story.
          const config = getCurrentInstance()!.appContext.config;
          config.errorHandler = () => {};
        },
        template: "<story />",
      };
    },
  ],
  play: async ({ canvasElement }) => {
    await waitFor(() =>
      expect(canvasElement.querySelector("[role='alert']")).not.toBeNull(),
    );
    await expect(canvasElement.querySelector(".md-editor-toolbar")).toBeNull();
  },
};
