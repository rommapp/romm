import type { StoryContext } from "@storybook/vue3-vite";
import { mount } from "@vue/test-utils";
import { expect, it, vi } from "vitest";
import { defineComponent, nextTick, reactive } from "vue";

it("keeps a pinned mode once the live listeners are installed", async () => {
  // vitest.setup.ts already loaded the decorator, so load a fresh copy with
  // its own modality singleton.
  vi.resetModules();
  const { useInputModality } =
    await import("@/v2/composables/useInputModality");
  const { withInputModality } = await import("../.storybook/withInputModality");
  useInputModality().install();

  const globals = reactive({ input: "key" });
  const story = defineComponent({ render: () => null });
  mount(
    withInputModality(
      story as unknown as Parameters<typeof withInputModality>[0],
      { globals } as unknown as StoryContext,
    ),
  );

  window.dispatchEvent(new Event("touchstart"));
  await nextTick();

  expect(document.documentElement.dataset.input).toBe("key");
});
