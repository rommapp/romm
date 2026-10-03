/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import AgeLimitFields from "./AgeLimitFields.vue";

vi.mock("vue-i18n");

const RSelect = defineComponent({
  props: {
    modelValue: { type: [String, Number], default: null },
    items: { type: Array, default: () => [] },
  },
  emits: ["update:modelValue"],
  template: `<select :value="modelValue" @change="$emit('update:modelValue', items[$event.target.selectedIndex].value)">
    <option v-for="item in items" :key="item.value" :value="item.value">{{ item.title }}</option>
  </select>`,
});

const RSwitch = defineComponent({
  props: { modelValue: { type: Boolean, default: false } },
  emits: ["update:modelValue"],
  template: `<input type="checkbox" :checked="modelValue" @change="$emit('update:modelValue', $event.target.checked)" />`,
});

interface FieldProps {
  ageLimit: number | null;
  hideUnrated: boolean | null;
  inherited?: { ageLimit: number | null; hideUnrated: boolean };
}

function mountFields(props: FieldProps) {
  return mount(AgeLimitFields, {
    props: { exemptRomIds: [], ...props },
    global: { stubs: { RSelect, RSwitch, HiddenGamesPicker: true } },
  });
}

describe("AgeLimitFields", () => {
  it("lets a group pick a limit or none", async () => {
    const wrapper = mountFields({ ageLimit: 12, hideUnrated: false });
    const select = wrapper.get("select");

    expect(select.element.value).toBe("12");
    await select.setValue("unset");
    await select.setValue("16");

    expect(wrapper.emitted("update:ageLimit")).toEqual([[null], [16]]);
  });

  it("keeps a limit outside the usual ages selected", () => {
    const wrapper = mountFields({ ageLimit: 14, hideUnrated: false });

    expect(wrapper.get("select").element.value).toBe("14");
  });

  it("toggles the unrated switch for a group", async () => {
    const wrapper = mountFields({ ageLimit: null, hideUnrated: false });

    await wrapper.get("input[type='checkbox']").setValue(true);

    expect(wrapper.emitted("update:hideUnrated")).toEqual([[true]]);
  });

  it("offers a user the group's settings, shown by value", async () => {
    const wrapper = mountFields({
      ageLimit: null,
      hideUnrated: null,
      inherited: { ageLimit: 12, hideUnrated: true },
    });
    const age = wrapper.get(".r-v2-age-limit__field:nth-child(1) select");
    const unrated = wrapper.get(".r-v2-age-limit__field:nth-child(2) select");

    expect(age.get("option").text()).toBe(
      'settings.age-limit-inherit:{"setting":"settings.age-limit-option:{\\"age\\":12}"}',
    );
    expect(unrated.get("option").text()).toBe(
      'settings.age-limit-inherit:{"setting":"settings.hide-unrated-games"}',
    );

    await unrated.setValue("show");
    await unrated.setValue("unset");

    expect(wrapper.emitted("update:hideUnrated")).toEqual([[false], [null]]);
  });
});
