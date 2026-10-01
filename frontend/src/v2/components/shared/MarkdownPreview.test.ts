// @vitest-environment-options { "settings": { "disableCSSFileLoading": true, "disableJavaScriptFileLoading": true } }
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import MarkdownPreview from "@/v2/components/shared/MarkdownPreview.vue";

async function render(markdown: string) {
  const wrapper = mount(MarkdownPreview, {
    props: { modelValue: markdown },
    attrs: { class: "caller-class" },
    attachTo: document.body,
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
});
