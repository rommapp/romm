// @vitest-environment-options { "settings": { "disableCSSFileLoading": true, "disableJavaScriptFileLoading": true } }
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import i18n from "@/locales";
import { MD_EDITOR_LOADER, loadMdEditor } from "@/plugins/mdeditor";
import MarkdownEditor from "@/v2/components/shared/MarkdownEditor.vue";

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
            [MD_EDITOR_LOADER as symbol]: () => new Promise(() => {}),
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
      .fn<() => ReturnType<typeof loadMdEditor>>()
      .mockRejectedValueOnce(new Error("chunk failed"))
      .mockImplementation(loadMdEditor);
    const wrapper = mount(MarkdownEditor, {
      props: { modelValue: "# Hello" },
      attachTo: document.body,
      global: {
        plugins: [i18n],
        provide: { [MD_EDITOR_LOADER as symbol]: loader },
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
