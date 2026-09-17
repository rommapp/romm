import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, type PropType } from "vue";
import UploadAssetDialog, {
  type UploadAssetPayload,
} from "./UploadAssetDialog.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/locales", () => ({
  default: { global: { t: (key: string) => key } },
}));

const formValid = { value: true };

const RDialog = {
  props: { modelValue: { type: Boolean, default: false } },
  template: `<div v-if="modelValue"><slot name="header" /><slot name="content" /><slot name="footer" /></div>`,
};
const RForm = {
  methods: {
    validate: async () => ({ valid: formValid.value }),
  },
  template: `<form><slot /></form>`,
};
// Emits the raw item in object mode and its value otherwise, like RSelect.
const RSelect = defineComponent({
  props: {
    modelValue: {
      type: null as unknown as PropType<unknown>,
      default: undefined,
    },
    items: { type: Array as PropType<unknown[]>, default: () => [] },
    itemTitle: {
      type: [String, Function] as PropType<
        string | ((item: unknown) => string)
      >,
      default: "title",
    },
    returnObject: { type: Boolean, default: false },
  },
  emits: ["update:modelValue"],
  setup(props, { emit }) {
    const titleOf = (item: unknown) =>
      typeof props.itemTitle === "function"
        ? props.itemTitle(item)
        : (item as Record<string, string>)[props.itemTitle];
    const pick = (event: Event) => {
      const index = (event.target as HTMLSelectElement).selectedIndex;
      const item = props.items[index] as { value?: unknown };
      emit("update:modelValue", props.returnObject ? item : item.value);
    };
    return { titleOf, pick };
  },
  template: `<select @change="pick"><option v-for="(i, n) in items" :key="n">{{ titleOf(i) }}</option></select>`,
});
const RTextField = {
  props: { modelValue: { type: String, default: "" } },
  emits: ["update:modelValue"],
  template: `<input class="slot-name" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`,
};
const RDropzone = {
  emits: ["files"],
  setup(
    _props: unknown,
    { emit }: { emit: (event: "files", files: File[]) => void },
  ) {
    return { pick: () => emit("files", [new File(["x"], "game.srm")]) };
  },
  template: `<button class="dropzone" @click="pick" />`,
};
const RBtn = {
  props: { disabled: { type: Boolean, default: false } },
  emits: ["click"],
  template: `<button class="btn" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
};

function mountDialog(
  type: "save" | "state",
  initialFiles: File[] = [],
  modelValue = true,
) {
  return mount(UploadAssetDialog, {
    props: {
      modelValue,
      type,
      saves: [{ slot: "main_quest" }, { slot: null }],
      cores: ["mgba", "builtin"],
      initialFiles,
    },
    global: {
      stubs: {
        RDialog,
        RForm,
        RSelect,
        RTextField,
        RDropzone,
        RBtn,
        RChip: true,
        RIcon: true,
      },
    },
  });
}

function uploadButton(wrapper: ReturnType<typeof mountDialog>) {
  return wrapper.findAll("button.btn").at(-1)!;
}

async function choose(
  wrapper: ReturnType<typeof mountDialog>,
  select: number,
  index: number,
) {
  const el = wrapper.findAll("select")[select].element;
  el.selectedIndex = index;
  await wrapper.findAll("select")[select].trigger("change");
}

async function submitted(wrapper: ReturnType<typeof mountDialog>) {
  await uploadButton(wrapper).trigger("click");
  await nextTick();
  return (
    wrapper.emitted("submit")?.[0] as [UploadAssetPayload] | undefined
  )?.[0];
}

describe("UploadAssetDialog", () => {
  afterEach(() => {
    formValid.value = true;
  });

  it("keeps Upload disabled until a file is picked, then uploads into autosave", async () => {
    const wrapper = mountDialog("save");
    expect(uploadButton(wrapper).attributes("disabled")).toBeDefined();

    await wrapper.get(".dropzone").trigger("click");
    expect(uploadButton(wrapper).attributes("disabled")).toBeUndefined();

    const payload = await submitted(wrapper);
    expect(payload).toMatchObject({
      type: "save",
      slot: "autosave",
      emulator: null,
    });
    expect(payload!.files.map((f) => f.name)).toEqual(["game.srm"]);
  });

  it("offers a new slot first, then autosave, the slots in use and no slot", async () => {
    const wrapper = mountDialog("save", [new File(["x"], "a.srm")]);
    const options = wrapper.findAll("select")[0].findAll("option");

    expect(options.map((o) => o.text())).toEqual([
      "play.new-slot",
      "autosave",
      "main_quest",
      "play.slot-none",
    ]);

    await choose(wrapper, 0, 2);
    expect(await submitted(wrapper)).toMatchObject({ slot: "main_quest" });
  });

  it("uploads as an archive when no slot is picked", async () => {
    const wrapper = mountDialog("save", [new File(["x"], "a.srm")]);
    await choose(wrapper, 0, 3);

    expect(await submitted(wrapper)).toMatchObject({ slot: null });
  });

  it("names a new slot and asks saves for nothing else", async () => {
    const wrapper = mountDialog("save", [new File(["x"], "a.srm")]);
    expect(wrapper.findAll("select")).toHaveLength(1);
    await choose(wrapper, 0, 0);
    await wrapper.get("input.slot-name").setValue("  speedrun ");

    expect(await submitted(wrapper)).toMatchObject({
      slot: "speedrun",
      emulator: null,
    });
  });

  it("does not submit while the form is invalid", async () => {
    formValid.value = false;
    const wrapper = mountDialog("save", [new File(["x"], "a.srm")]);
    await choose(wrapper, 0, 0);

    expect(await submitted(wrapper)).toBeUndefined();
  });

  it("asks states only for the core", async () => {
    const wrapper = mountDialog("state", [new File(["x"], "a.state")]);
    expect(wrapper.findAll("select")).toHaveLength(1);

    expect(wrapper.findAll("option").map((o) => o.text())).toEqual([
      "play.any-core",
      "mgba",
      "builtin",
    ]);

    await choose(wrapper, 0, 2);
    expect(await submitted(wrapper)).toMatchObject({
      slot: null,
      emulator: "builtin",
    });
  });

  it("starts from the dropped files every time it opens", async () => {
    const wrapper = mountDialog("save", [], false);
    await wrapper.setProps({
      modelValue: true,
      initialFiles: [new File(["x"], "dropped.srm")],
    });

    expect(uploadButton(wrapper).attributes("disabled")).toBeUndefined();
    expect((await submitted(wrapper))!.files.map((f) => f.name)).toEqual([
      "dropped.srm",
    ]);
  });
});
