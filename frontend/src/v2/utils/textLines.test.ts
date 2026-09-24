import { describe, expect, it } from "vitest";
import { wrappedLineCount } from "@/v2/utils/textLines";

// Every character is 10px wide.
const measure = (run: string) => run.length * 10;

describe("wrappedLineCount", () => {
  it("keeps text that fits on one line", () => {
    expect(wrappedLineCount("Signed in", 100, measure)).toBe(1);
  });

  it("moves the word that doesn't fit to the next line", () => {
    expect(wrappedLineCount("Played Metroid today", 140, measure)).toBe(2);
    expect(wrappedLineCount("aaaa bbbb cccc dddd", 90, measure)).toBe(2);
    expect(wrappedLineCount("aaaa bbbb cccc dddd", 80, measure)).toBe(4);
  });

  it("breaks a word longer than a line wherever it must", () => {
    expect(
      wrappedLineCount("不明なユーザ名でのログインに失敗しました", 50, measure),
    ).toBe(4);
    expect(wrappedLineCount("go aaaaaaaaaaaa", 50, measure)).toBe(4);
  });

  it("stops counting at the most lines shown", () => {
    expect(wrappedLineCount("aaaa bbbb cccc dddd", 80, measure, 2)).toBe(2);
    expect(wrappedLineCount("go aaaaaaaaaaaa", 50, measure, 3)).toBe(3);
  });

  it("counts one line for no text or no room", () => {
    expect(wrappedLineCount("", 100, measure)).toBe(1);
    expect(wrappedLineCount("Signed in", 0, measure)).toBe(1);
  });
});
