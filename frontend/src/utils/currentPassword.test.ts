import { describe, expect, it } from "vitest";
import { needsCurrentPassword } from "./currentPassword";

const saved = { email: "me@example.com", has_password: true };

describe("needsCurrentPassword", () => {
  it("asks for it when setting a new password", () => {
    expect(needsCurrentPassword(saved, { password: "a_new_password" })).toBe(
      true,
    );
  });

  it("asks for it when the email changes or is cleared", () => {
    expect(needsCurrentPassword(saved, { email: "new@example.com" })).toBe(
      true,
    );
    expect(needsCurrentPassword(saved, { email: "" })).toBe(true);
  });

  it("skips it when the email only differs by case", () => {
    expect(needsCurrentPassword(saved, { email: "Me@Example.com" })).toBe(
      false,
    );
  });

  it("skips it when neither the password nor the email changes", () => {
    expect(
      needsCurrentPassword(saved, { password: "", email: "me@example.com" }),
    ).toBe(false);
  });

  it("skips it for an account without a password", () => {
    expect(
      needsCurrentPassword(
        { email: null, has_password: false },
        { password: "a_first_password", email: "new@example.com" },
      ),
    ).toBe(false);
  });
});
