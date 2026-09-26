import type { StoryContext } from "@storybook/vue3-vite";
import { mount } from "@vue/test-utils";
import { expect, it } from "vitest";
import { defineComponent, nextTick, reactive } from "vue";
import { useInputModality } from "@/v2/composables/useInputModality";
import { withInputModality } from "../.storybook/withInputModality";

it("pins the toolbar's mode over live input and follows a toolbar change", async () => {
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
  expect(document.documentElement.dataset.input).toBe("key");

  globals.input = "touch";
  await nextTick();
  expect(document.documentElement.dataset.input).toBe("touch");
});
