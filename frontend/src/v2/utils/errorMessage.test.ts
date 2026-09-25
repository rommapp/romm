import { AxiosError } from "axios";
import { describe, expect, it } from "vitest";
import { errorMessage } from "./errorMessage";

function refused(detail: unknown): AxiosError {
  return Object.assign(new AxiosError("Request failed with status code 400"), {
    response: { data: { detail } },
  }) as AxiosError;
}

describe("errorMessage", () => {
  it("prefers the server's own detail to the fallback", () => {
    expect(errorMessage(refused("Name taken"), "Could not save")).toBe(
      "Name taken",
    );
  });

  it("puts the fallback in place of axios' generic message", () => {
    expect(errorMessage(refused([{ loc: ["body"] }]), "Could not save")).toBe(
      "Could not save",
    );
    expect(errorMessage(new Error("boom"), "Could not save")).toBe(
      "Could not save",
    );
  });

  it("keeps axios' message without a fallback", () => {
    expect(errorMessage(refused(undefined))).toBe(
      "Request failed with status code 400",
    );
  });
});
