import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Events } from "@/types/emitter";
import ConfirmDialog from "./ConfirmDialog.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const RBtnStub = {
  props: { disabled: { type: Boolean, default: false } },
  template: "<button :disabled='disabled'><slot /></button>",
};

function mountDialog(emitter: Emitter<Events>): VueWrapper {
  return mount(ConfirmDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog: {
          props: { modelValue: { type: Boolean, default: false } },
          template:
            "<div v-if='modelValue'><slot name='content' /><slot name='footer' /></div>",
        },
        RBtn: RBtnStub,
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

async function promptFor(requireTyped: string): Promise<VueWrapper> {
  const emitter = mitt<Events>();
  const wrapper = mountDialog(emitter);
  emitter.emit("showConfirm", {
    id: 1,
    title: "Delete platform",
    requireTyped,
  } as Events["showConfirm"]);
  await flushPromises();
  return wrapper;
}

function confirmButton(wrapper: VueWrapper) {
  return wrapper.findAll("button")[1];
}

describe("ConfirmDialog typed confirmation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("keeps the action disabled until the phrase is typed", async () => {
    const wrapper = await promptFor("Philips Videopac+");
    expect(confirmButton(wrapper).attributes("disabled")).toBeDefined();

    await wrapper.find("input").setValue("Philips Videopac");
    expect(confirmButton(wrapper).attributes("disabled")).toBeDefined();

    await wrapper.find("input").setValue("Philips Videopac+");
    expect(confirmButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  // The hint collapses runs of whitespace when it renders, so the only
  // spelling the user can read back is the collapsed one.
  it("accepts the phrase as rendered when the stored one has a double space", async () => {
    const wrapper = await promptFor("Philips Videopac+  (Retool)");

    await wrapper.find("input").setValue("Philips Videopac+ (Retool)");

    expect(confirmButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  it("keeps the action disabled when the phrase is whitespace only", async () => {
    const wrapper = await promptFor("   ");
    expect(confirmButton(wrapper).attributes("disabled")).toBeDefined();

    await wrapper.find("input").setValue("   ");
    expect(confirmButton(wrapper).attributes("disabled")).toBeUndefined();
  });

  // A no-break space survives rendering, so it is not interchangeable with
  // the plain space the user would type.
  it("treats a no-break space as a character of its own", async () => {
    const wrapper = await promptFor("Philips\u00a0Videopac+");

    await wrapper.find("input").setValue("Philips Videopac+");
    expect(confirmButton(wrapper).attributes("disabled")).toBeDefined();

    await wrapper.find("input").setValue("Philips\u00a0Videopac+");
    expect(confirmButton(wrapper).attributes("disabled")).toBeUndefined();
  });
});
