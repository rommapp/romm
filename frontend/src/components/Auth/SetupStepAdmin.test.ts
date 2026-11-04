import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defaultAvatarPath } from "@/utils";
import SetupStepAdmin, { type AdminUserDraft } from "./SetupStepAdmin.vue";

vi.mock("vue-i18n");

function draft(avatar?: File): AdminUserDraft {
  return { username: "", email: "", password: "", repeatPassword: "", avatar };
}

function mountStep(avatar?: File) {
  return mount(SetupStepAdmin, {
    props: { modelValue: draft(avatar) },
    global: {
      stubs: {
        RBtn: true,
        RForm: { template: "<form><slot /></form>" },
        RIcon: true,
        RTextField: true,
        RTooltip: true,
        PasswordField: true,
      },
    },
  });
}

describe("SetupStepAdmin avatar preview", () => {
  let urls = 0;

  beforeEach(() => {
    urls = 0;
    vi.spyOn(URL, "createObjectURL").mockImplementation(() => `blob:${++urls}`);
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);
  });

  it("shows the default avatar until a file is picked", () => {
    const wrapper = mountStep();

    expect(wrapper.get("img").attributes("src")).toBe(defaultAvatarPath);
    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it("previews the picked file and revokes each URL it replaces", async () => {
    const wrapper = mountStep(new File(["a"], "a.png"));
    expect(wrapper.get("img").attributes("src")).toBe("blob:1");

    await wrapper.setProps({ modelValue: draft(new File(["b"], "b.png")) });

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
    expect(wrapper.get("img").attributes("src")).toBe("blob:2");
  });

  it("revokes the preview on unmount", () => {
    const wrapper = mountStep(new File(["a"], "a.png"));

    wrapper.unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
  });
});
