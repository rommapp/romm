// @vitest-environment-options { "settings": { "disableCSSFileLoading": true, "disableJavaScriptFileLoading": true } }
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import i18n from "@/locales";
import { MD_EDITOR_LOADER, loadMdEditor } from "@/plugins/mdeditor";
import MarkdownPreview from "@/v2/components/shared/MarkdownPreview.vue";

async function render(
  markdown: string,
  options?: { global?: Record<string, unknown> },
) {
  const wrapper = mount(MarkdownPreview, {
    props: { modelValue: markdown },
    attrs: { class: "caller-class" },
    attachTo: document.body,
    ...options,
  });
  await vi.waitFor(() => {
    expect(wrapper.find(".md-editor-preview").exists()).toBe(true);
    expect(wrapper.find(".md-editor-preview").element.innerHTML).not.toBe("");
  });
  await flushPromises();
  return wrapper;
}

describe("MarkdownPreview", () => {
  it("renders through the configured loader, so raw HTML is sanitized", async () => {
    const wrapper = await render(
      '<img src="/x.png" onerror="alert(1)">\n\n<script>alert(2)</script>',
    );
    const preview = wrapper.find(".md-editor-preview").element;

    const img = preview.querySelector('img[src="/x.png"]');
    expect(img).not.toBeNull();
    expect(img?.hasAttribute("onerror")).toBe(false);
    expect(preview.querySelector("script")).toBeNull();
    wrapper.unmount();
  });

  it("forwards caller attributes to the editor root", async () => {
    const wrapper = await render("# Title");

    expect(wrapper.find(".md-editor.caller-class").exists()).toBe(true);
    wrapper.unmount();
  });

  it("shows a skeleton while the loader is pending", async () => {
    vi.useFakeTimers();
    try {
      const wrapper = mount(MarkdownPreview, {
        props: { modelValue: "# Title" },
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
      expect(wrapper.find(".md-editor-preview").exists()).toBe(false);
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
    const wrapper = mount(MarkdownPreview, {
      props: { modelValue: "# Title" },
      attachTo: document.body,
      global: {
        plugins: [i18n],
        provide: { [MD_EDITOR_LOADER as symbol]: loader },
      },
    });
    await vi.waitFor(() => {
      expect(wrapper.find("[role='alert']").exists()).toBe(true);
    });
    expect(wrapper.find(".md-editor-preview").exists()).toBe(false);

    await wrapper.find("button").trigger("click");

    await vi.waitFor(() => {
      expect(wrapper.find(".md-editor-preview").exists()).toBe(true);
    });
    expect(loader).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });
});
