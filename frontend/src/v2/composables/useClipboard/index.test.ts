import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useClipboard } from "./index";

const success = vi.fn();
const error = vi.fn();

vi.mock("vue-i18n", () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) =>
      params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success, error }),
}));

function setSecureContext(value: boolean) {
  Object.defineProperty(window, "isSecureContext", {
    configurable: true,
    value,
  });
}

function setClipboard(writeText: ((text: string) => Promise<void>) | null) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: writeText ? { writeText } : undefined,
  });
}

beforeEach(() => {
  success.mockClear();
  error.mockClear();
});

afterEach(() => {
  setClipboard(null);
});

describe("useClipboard", () => {
  it("writes the text and shows the success toast in a secure context", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setSecureContext(true);
    setClipboard(writeText);

    const { copy } = useClipboard();
    const ok = await copy("hello", { successMessage: "copied" });

    expect(ok).toBe(true);
    expect(writeText).toHaveBeenCalledWith("hello");
    expect(success).toHaveBeenCalledWith("copied", { icon: "mdi-check-bold" });
    expect(error).not.toHaveBeenCalled();
  });

  it("shows no success toast when successMessage is omitted", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setSecureContext(true);
    setClipboard(writeText);

    const { copy } = useClipboard();
    const ok = await copy("hello");

    expect(ok).toBe(true);
    expect(success).not.toHaveBeenCalled();
  });

  it("errors without touching the clipboard when the context is not secure", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setSecureContext(false);
    setClipboard(writeText);

    const { copy } = useClipboard();
    const ok = await copy("hello", { successMessage: "copied" });

    expect(ok).toBe(false);
    expect(writeText).not.toHaveBeenCalled();
    expect(error).toHaveBeenCalledWith("common.clipboard-copy-failed", {
      icon: "mdi-close-circle",
    });
  });

  it("errors when the Clipboard API is unavailable", async () => {
    setSecureContext(true);
    setClipboard(null);

    const { copy } = useClipboard();
    const ok = await copy("hello");

    expect(ok).toBe(false);
    expect(error).toHaveBeenCalledWith("common.clipboard-copy-failed", {
      icon: "mdi-close-circle",
    });
  });

  it("errors when writeText rejects", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    setSecureContext(true);
    setClipboard(writeText);

    const { copy } = useClipboard();
    const ok = await copy("hello", { successMessage: "copied" });

    expect(ok).toBe(false);
    expect(success).not.toHaveBeenCalled();
    expect(error).toHaveBeenCalledWith("common.clipboard-copy-failed", {
      icon: "mdi-close-circle",
    });
  });

  it("uses a custom error message when provided", async () => {
    setSecureContext(false);
    setClipboard(null);

    const { copy } = useClipboard();
    await copy("hello", { errorMessage: "nope" });

    expect(error).toHaveBeenCalledWith("nope", { icon: "mdi-close-circle" });
  });
});
