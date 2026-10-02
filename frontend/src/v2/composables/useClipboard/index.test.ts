import { afterEach, describe, expect, it, vi } from "vitest";
import { useClipboard } from "./index";

const success = vi.fn();
const error = vi.fn();

vi.mock("vue-i18n");

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success, error }),
}));

function setSecureContext(value: boolean) {
  vi.stubGlobal("isSecureContext", value);
}

function setClipboard(writeText: ((text: string) => Promise<void>) | null) {
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: writeText ? { writeText } : undefined,
  });
}

function setExecCommand(result: boolean | null) {
  const execCommand = result === null ? undefined : vi.fn(() => result);
  Object.defineProperty(document, "execCommand", {
    configurable: true,
    value: execCommand,
  });
  return execCommand;
}

afterEach(() => {
  setClipboard(null);
  setExecCommand(null);
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

  it("falls back to execCommand when the context is not secure", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setSecureContext(false);
    setClipboard(writeText);
    const execCommand = setExecCommand(true);

    const { isSupported, copy } = useClipboard();
    const ok = await copy("hello", { successMessage: "copied" });

    expect(isSupported).toBe(true);
    expect(ok).toBe(true);
    expect(writeText).not.toHaveBeenCalled();
    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(success).toHaveBeenCalledWith("copied", { icon: "mdi-check-bold" });
    expect(document.querySelector("textarea")).toBeNull();
  });

  it("hands focus back to the trigger after the fallback copy", async () => {
    setSecureContext(false);
    setExecCommand(true);
    const trigger = document.createElement("button");
    document.body.appendChild(trigger);
    trigger.focus();

    const { copy } = useClipboard();
    await copy("hello");

    expect(document.activeElement).toBe(trigger);
    trigger.remove();
  });

  it("shows the HTTPS hint when the fallback copy fails", async () => {
    setSecureContext(false);
    setExecCommand(false);

    const { copy } = useClipboard();
    const ok = await copy("hello", { successMessage: "copied" });

    expect(ok).toBe(false);
    expect(success).not.toHaveBeenCalled();
    expect(error).toHaveBeenCalledWith("common.clipboard-copy-failed", {
      icon: "mdi-close-circle",
    });
  });

  it("is unsupported when neither the Clipboard API nor execCommand exists", async () => {
    setSecureContext(true);
    setClipboard(null);

    const { isSupported, copy } = useClipboard();
    const ok = await copy("hello");

    expect(isSupported).toBe(false);
    expect(ok).toBe(false);
    expect(error).toHaveBeenCalledWith("common.clipboard-copy-failed", {
      icon: "mdi-close-circle",
    });
  });

  it("falls back to execCommand when writeText rejects", async () => {
    setSecureContext(true);
    setClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    setExecCommand(true);

    const { copy } = useClipboard();
    const ok = await copy("hello", { successMessage: "copied" });

    expect(ok).toBe(true);
    expect(error).not.toHaveBeenCalled();
  });

  it("errors without the HTTPS hint when writeText rejects", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    setSecureContext(true);
    setClipboard(writeText);
    setExecCommand(false);

    const { copy } = useClipboard();
    const ok = await copy("hello", { successMessage: "copied" });

    expect(ok).toBe(false);
    expect(success).not.toHaveBeenCalled();
    expect(error).toHaveBeenCalledWith("common.clipboard-write-failed", {
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

  it("runs the fallback instead of the error toast when the context is not secure", async () => {
    setSecureContext(false);
    setClipboard(null);
    const fallback = vi.fn();

    const { copy } = useClipboard();
    const ok = await copy("hello", { fallback });

    expect(ok).toBe(false);
    expect(fallback).toHaveBeenCalledOnce();
    expect(error).not.toHaveBeenCalled();
  });

  it("runs the fallback when writeText rejects", async () => {
    setSecureContext(true);
    setClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    const fallback = vi.fn();

    const { copy } = useClipboard();
    await copy("hello", { successMessage: "copied", fallback });

    expect(fallback).toHaveBeenCalledOnce();
    expect(success).not.toHaveBeenCalled();
    expect(error).not.toHaveBeenCalled();
  });
});
