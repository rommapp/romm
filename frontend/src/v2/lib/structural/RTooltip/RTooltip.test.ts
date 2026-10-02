import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, ref } from "vue";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "@/v2/lib/overlays/RDialog/escapeStack";
import RTooltip from "./RTooltip.vue";

describe("RTooltip", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("anchors to the activator a `v-if` swapped in", async () => {
    const panel = document.createElement("div");
    document.body.append(panel);
    const swapped = ref(false);
    const Host = defineComponent({
      components: { RTooltip },
      setup: () => ({ swapped }),
      template: `
        <RTooltip text="Tip" :open-delay="0">
          <template #activator="{ props }">
            <button v-if="!swapped" type="button" class="a" v-bind="props">A</button>
            <button v-else type="button" class="b" v-bind="props">B</button>
          </template>
        </RTooltip>`,
    });
    const wrapper = mount(Host, { attachTo: panel });
    const dialog: EscapableEntry = {
      close: vi.fn(),
      persistent: false,
      panel: () => panel,
    };
    pushEscapable(dialog);
    swapped.value = true;
    await nextTick();

    await wrapper
      .get("button.b")
      .trigger("pointerenter", { pointerType: "mouse" });
    await flushPromises();

    expect(document.querySelector(".r-tooltip")).not.toBeNull();
    popEscapable(dialog);
    wrapper.unmount();
  });
});
