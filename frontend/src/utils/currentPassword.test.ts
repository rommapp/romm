import { describe, expect, it } from "vitest";
import { needsCurrentPassword } from "./currentPassword";

const saved = {
  username: "me",
  email: "me@example.com",
  has_password: true,
};

describe("needsCurrentPassword", () => {
  it.each([
    ["a new password", saved, { password: "a_new_password" }, true],
    ["a new username", saved, { username: "someone_else" }, true],
    ["a username that only differs by case", saved, { username: "Me" }, false],
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
      { username: "me", email: null, has_password: false },
      {
        username: "someone_else",
        password: "a_first_password",
        email: "new@example.com",
      },
      false,
    ],
  ])("for %s", (_label, account, edit, expected) => {
    expect(needsCurrentPassword(account, edit)).toBe(expected);
  });
});
