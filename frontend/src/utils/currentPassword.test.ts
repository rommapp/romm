import { describe, expect, it } from "vitest";
import { needsCurrentPassword } from "./currentPassword";

const saved = { email: "me@example.com", has_password: true };

describe("needsCurrentPassword", () => {
  it.each([
    ["a new password", saved, { password: "a_new_password" }, true],
    ["a changed email", saved, { email: "new@example.com" }, true],
    ["a cleared email", saved, { email: "" }, true],
    [
      "an email that only differs by case",
      saved,
      { email: "Me@Example.com" },
      false,
    ],
    [
      "no password or email change",
      saved,
      { password: "", email: "me@example.com" },
      false,
    ],
    [
      "an account without a password",
      { email: null, has_password: false },
      { password: "a_first_password", email: "new@example.com" },
      false,
    ],
  ])("for %s", (_label, account, edit, expected) => {
    expect(needsCurrentPassword(account, edit)).toBe(expected);
  });
});
