import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { channelFixture } from "@/v2/utils/snapshots.fixtures";
import DeleteChannelDialog from "./DeleteChannelDialog.vue";

vi.mock("vue-i18n");

function mountDialog(onConfirm: () => Promise<void>) {
  return mount(DeleteChannelDialog, {
    props: { channel: channelFixture({ label: "Main" }), body: "", onConfirm },
    global: {
      stubs: {
        RDialog: {
          props: { modelValue: { type: Boolean, default: false } },
          template:
            "<div v-if='modelValue'><slot name='content' /><slot name='footer-start' /><slot name='footer' /></div>",
        },
        RBtn: {
          props: {
            disabled: { type: Boolean, default: false },
            loading: { type: Boolean, default: false },
          },
          template:
            "<button :disabled='disabled' :data-loading='loading'><slot /></button>",
        },
        RTextField: {
          props: { modelValue: { type: String, default: "" } },
          emits: ["update:modelValue"],
          template:
            "<input :value='modelValue' @input=\"$emit('update:modelValue', $event.target.value)\" />",
        },
        "i18n-t": { template: "<p><slot name='label' /></p>" },
      },
    },
  });
}

describe("DeleteChannelDialog", () => {
  it("deletes only once the label is typed", async () => {
    const onConfirm = vi.fn(() => Promise.resolve());
    const wrapper = mountDialog(onConfirm);
    const [, remove] = wrapper.findAll("button");

    await remove!.trigger("click");
    expect(onConfirm).not.toHaveBeenCalled();

    await wrapper.find("input").setValue("Main");
    await remove!.trigger("click");
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("blocks cancel and shows progress while the delete runs, then stays open on failure", async () => {
    let fail: () => void = () => undefined;
    const wrapper = mountDialog(
      () =>
        new Promise((_, reject) => {
          fail = () => reject(new Error("offline"));
        }),
    );
    await wrapper.find("input").setValue("Main");
    await wrapper.findAll("button")[1]!.trigger("click");

    const [cancel, remove] = wrapper.findAll("button");
    expect(cancel!.attributes("disabled")).toBeDefined();
    expect(remove!.attributes("data-loading")).toBe("true");

    fail();
    await flushPromises();

    expect(
      wrapper.findAll("button")[0]!.attributes("disabled"),
    ).toBeUndefined();
    expect(wrapper.emitted("close")).toBeUndefined();
    expect(wrapper.find("input").exists()).toBe(true);
  });
});
