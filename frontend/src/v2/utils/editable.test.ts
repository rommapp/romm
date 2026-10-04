import { describe, expect, it } from "vitest";
import { isEditable } from "./editable";

describe("isEditable", () => {
  it.each(["input", "textarea", "select"])("is true for a <%s>", (tag) => {
    expect(isEditable(document.createElement(tag))).toBe(true);
  });

  it("is true for contenteditable content", () => {
    const el = document.createElement("div");
    el.contentEditable = "true";
    document.body.append(el);

    expect(isEditable(el)).toBe(true);
    el.remove();
  });

  it("is false for a button, the document and nothing", () => {
    expect(isEditable(document.createElement("button"))).toBe(false);
    expect(isEditable(document)).toBe(false);
    expect(isEditable(null)).toBe(false);
  });
});
