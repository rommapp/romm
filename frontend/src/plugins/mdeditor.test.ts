// @vitest-environment-options { "settings": { "disableCSSFileLoading": true, "disableJavaScriptFileLoading": true } }
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { loadMdEditor } from "./mdeditor";

async function render(markdown: string): Promise<HTMLElement> {
  const { MdPreview } = await loadMdEditor();
  const wrapper = mount(MdPreview, {
    props: { id: "mdeditor-test", modelValue: markdown },
    attachTo: document.body,
  });
  await vi.waitFor(() => {
    expect(wrapper.find(".md-editor-preview").element.innerHTML).not.toBe("");
  });
  await flushPromises();
  const preview = wrapper.find(".md-editor-preview").element as HTMLElement;
  wrapper.unmount();
  return preview;
}

describe("loadMdEditor", () => {
  it("loads and configures the library once", async () => {
    const first = loadMdEditor();
    expect(loadMdEditor()).toBe(first);
    expect(await first).toBe(await loadMdEditor());
  });

  it("renders raw HTML in markdown", async () => {
    const preview = await render('line<br>next\n\n<img src="/shot.png">');

    expect(preview.querySelector("br")).not.toBeNull();
    expect(preview.querySelector('img[src="/shot.png"]')).not.toBeNull();
    expect(preview.textContent).not.toContain("<img");
  });

  it("strips script and event handlers from raw HTML", async () => {
    const preview = await render(
      '<img src="/x.png" onerror="alert(1)">\n\n<script>alert(2)</script>',
    );

    const img = preview.querySelector('img[src="/x.png"]');
    expect(img).not.toBeNull();
    expect(img?.hasAttribute("onerror")).toBe(false);
    expect(preview.querySelector("script")).toBeNull();
  });
});
