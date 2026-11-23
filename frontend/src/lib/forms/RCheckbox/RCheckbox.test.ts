import { parse as parseSfc } from "@vue/compiler-sfc";
import { mount } from "@vue/test-utils";
import postcss from "postcss";
import type { Rule } from "postcss";
import { describe, expect, it } from "vitest";
import source from "./RCheckbox.vue?raw";
import { RCheckbox } from "./index";

// happy-dom has no layout, so the stylesheet is checked directly.
function declarationsFor(selector: string): Record<string, string> {
  const { descriptor } = parseSfc(source);
  const decls: Record<string, string> = {};
  for (const style of descriptor.styles) {
    postcss.parse(style.content).walkRules((rule: Rule) => {
      if (!rule.selectors.includes(selector)) return;
      rule.walkDecls((decl) => {
        decls[decl.prop] = decl.value;
      });
    });
  }
  return decls;
}

describe("RCheckbox native input", () => {
  // An uncontained input sits outside its scrolling list, so focusing it
  // scrolls an `overflow: hidden` ancestor and blanks it.
  it("is positioned against the checkbox label", () => {
    expect(declarationsFor(".r-checkbox__input").position).toBe("absolute");
    expect(declarationsFor(".r-checkbox").position).toBe("relative");
  });
});

describe("RCheckbox decorative", () => {
  it("draws the box without an input or label", () => {
    const wrapper = mount(RCheckbox, {
      props: { modelValue: true, decorative: true },
    });

    expect(wrapper.find("input").exists()).toBe(false);
    expect(wrapper.find("label").exists()).toBe(false);
    expect(wrapper.find(".r-checkbox").attributes("aria-hidden")).toBe("true");
    expect(wrapper.classes()).toContain("r-checkbox--checked");
  });
});
