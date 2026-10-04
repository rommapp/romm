import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { UpdateRom } from "@/services/api/rom";
import { makeRom } from "@/utils/rom.fixtures";
import AdditionalDetails from "./AdditionalDetails.vue";

vi.mock("vue-i18n");

const RComboboxField = {
  props: { label: { type: String, default: "" } },
  emits: ["update:modelValue"],
  template: `<div />`,
};

function titlesField(wrapper: ReturnType<typeof mountDetails>) {
  const field = wrapper
    .findAllComponents(RComboboxField)
    .find((c) => c.props("label") === "rom.alternative-titles");
  if (!field) throw new Error("Alternative titles field not rendered");
  return field;
}

function mountDetails(rom: UpdateRom) {
  return mount(AdditionalDetails, {
    props: { rom },
    global: {
      stubs: { RComboboxField, RDateField: true, RTextField: true },
    },
  });
}

describe("AdditionalDetails alternative titles", () => {
  it("writes the titles into the manual metadata", async () => {
    const rom = makeRom({ manual_metadata: { genres: ["Racing"] } });
    const wrapper = mountDetails(rom);

    await titlesField(wrapper).vm.$emit("update:modelValue", ["ACNH"]);

    expect(wrapper.emitted("update:rom")?.[0]?.[0]).toMatchObject({
      manual_metadata: { genres: ["Racing"], alternative_names: ["ACNH"] },
    });
  });

  it("clears the titles", async () => {
    const rom = makeRom({ manual_metadata: { alternative_names: ["ACNH"] } });
    const wrapper = mountDetails(rom);

    await titlesField(wrapper).vm.$emit("update:modelValue", []);

    expect(wrapper.emitted("update:rom")?.[0]?.[0]).toMatchObject({
      manual_metadata: { alternative_names: [] },
    });
  });
});
