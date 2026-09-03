import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { nextTick } from "vue";
import UploadFilesDialog from "./UploadFilesDialog.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("@/locales", () => ({
  default: { global: { t: (key: string) => key } },
}));

const formValid = { value: true };

const RDialog = {
  props: ["modelValue"],
  template: `<div v-if="modelValue"><slot name="header" /><slot name="content" /><slot name="footer" /></div>`,
};
const RForm = {
  methods: {
    validate: async () => ({ valid: formValid.value }),
  },
  template: `<form><slot /></form>`,
};
const RSelect = {
  props: ["modelValue", "items"],
  emits: ["update:modelValue"],
  template: `<select class="dest" :value="modelValue" @change="$emit('update:modelValue', $event.target.value)"><option v-for="i in items" :key="i.value" :value="i.value">{{ i.title }}</option></select>`,
};
const RTextField = {
  props: ["modelValue"],
  emits: ["update:modelValue"],
  template: `<input class="folder" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`,
};
const RDropzone = {
  emits: ["files"],
  setup(
    _props: unknown,
    { emit }: { emit: (event: "files", files: File[]) => void },
  ) {
    return { pick: () => emit("files", [new File(["x"], "fix.ips")]) };
  },
  template: `<button class="dropzone" @click="pick" />`,
};
const RBtn = {
  props: ["disabled"],
  emits: ["click"],
  template: `<button class="btn" :disabled="disabled" @click="$emit('click')"><slot /></button>`,
};

function mountDialog(initialFolder = "") {
  return mount(UploadFilesDialog, {
    props: {
      modelValue: true,
      folders: [{ value: "hack", label: "Hack", icon: "mdi-pencil-ruler" }],
      initialFolder,
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

describe("UploadFilesDialog", () => {
  it("keeps Upload disabled until a file is picked, then emits the root", async () => {
    formValid.value = true;
    const wrapper = mountDialog();
    expect(uploadButton(wrapper).attributes("disabled")).toBeDefined();

    await wrapper.get(".dropzone").trigger("click");
    expect(uploadButton(wrapper).attributes("disabled")).toBeUndefined();
    await uploadButton(wrapper).trigger("click");
    await nextTick();

    const [payload] = wrapper.emitted("submit")![0] as [
      { folder: string; files: File[] },
    ];
    expect(payload.folder).toBe("");
    expect(payload.files.map((f) => f.name)).toEqual(["fix.ips"]);
  });

  it("preselects the active folder", async () => {
    const wrapper = mountDialog("hack");
    await wrapper.get(".dropzone").trigger("click");
    await uploadButton(wrapper).trigger("click");
    await nextTick();

    const [payload] = wrapper.emitted("submit")![0] as [{ folder: string }];
    expect(payload.folder).toBe("hack");
  });

  it("trims a new folder path before emitting it", async () => {
    const wrapper = mountDialog();
    await wrapper.get("select.dest").setValue("__new__");
    await wrapper.get("input.folder").setValue("patches/v2/");
    await wrapper.get(".dropzone").trigger("click");
    await uploadButton(wrapper).trigger("click");
    await nextTick();

    const [payload] = wrapper.emitted("submit")![0] as [{ folder: string }];
    expect(payload.folder).toBe("patches/v2");
  });

  it("does not submit while the form is invalid", async () => {
    formValid.value = false;
    const wrapper = mountDialog();
    await wrapper.get("select.dest").setValue("__new__");
    await wrapper.get("input.folder").setValue("../x");
    await wrapper.get(".dropzone").trigger("click");
    await uploadButton(wrapper).trigger("click");
    await nextTick();

    expect(wrapper.emitted("submit")).toBeUndefined();
    formValid.value = true;
  });

  it("starts fresh every time it opens", async () => {
    const wrapper = mountDialog();
    await wrapper.get(".dropzone").trigger("click");
    await wrapper.setProps({ modelValue: false });
    await wrapper.setProps({ modelValue: true, initialFolder: "hack" });

    expect(uploadButton(wrapper).attributes("disabled")).toBeDefined();
    expect(
      (wrapper.get("select.dest").element as HTMLSelectElement).value,
    ).toBe("hack");
  });
});
