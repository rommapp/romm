// @vitest-environment-options { "settings": { "disableCSSFileLoading": true, "disableJavaScriptFileLoading": true } }
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import i18n from "@/locales";
import MarkdownEditor from "@/v2/components/shared/MarkdownEditor.vue";
import { MD_LOADERS } from "@/v2/composables/useLazyMarkdown";

const loadEditor = () => import("@/v2/components/shared/markdownEditor");

describe("MarkdownEditor", () => {
  it("mounts the editor once the loader resolves", async () => {
    const wrapper = mount(MarkdownEditor, {
      props: { modelValue: "# Hello" },
      attachTo: document.body,
    });
    await vi.waitFor(() => {
      expect(wrapper.find(".md-editor-toolbar").exists()).toBe(true);
    });
    await flushPromises();

    expect(wrapper.text()).toContain("Hello");
    wrapper.unmount();
  });

  it("shows a skeleton while the loader is pending", async () => {
    vi.useFakeTimers();
    try {
      const wrapper = mount(MarkdownEditor, {
        props: { modelValue: "# Hello" },
        attachTo: document.body,
        global: {
          provide: {
            [MD_LOADERS as symbol]: { editor: () => new Promise(() => {}) },
          },
        },
      });
      // Advance past the 200ms defineAsyncComponent delay.
      await vi.advanceTimersByTimeAsync(300);
      await flushPromises();

      expect(wrapper.find(".r-skeleton").exists()).toBe(true);
      expect(wrapper.find(".md-editor-toolbar").exists()).toBe(false);
      wrapper.unmount();
    } finally {
      vi.useRealTimers();
    }
  });

  it("shows a retry when the loader fails and recovers on retry", async () => {
    const loader = vi
      .fn<() => ReturnType<typeof loadEditor>>()
      .mockRejectedValueOnce(new Error("chunk failed"))
      .mockImplementation(loadEditor);
    const wrapper = mount(MarkdownEditor, {
      props: { modelValue: "# Hello" },
      attachTo: document.body,
      global: {
        plugins: [i18n],
        provide: { [MD_LOADERS as symbol]: { editor: loader } },
      },
    });
    await vi.waitFor(() => {
      expect(wrapper.find("[role='alert']").exists()).toBe(true);
    });
    expect(wrapper.find(".md-editor-toolbar").exists()).toBe(false);

    await wrapper.find("button").trigger("click");

    await vi.waitFor(() => {
      expect(wrapper.find(".md-editor-toolbar").exists()).toBe(true);
    });
    expect(loader).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });
});
