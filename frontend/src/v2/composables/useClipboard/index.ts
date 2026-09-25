// useClipboard — copy text to the clipboard with consistent feedback.
// The browser Clipboard API only exists in a secure context (HTTPS or
// localhost). Over plain HTTP `navigator.clipboard` is undefined, so callers
// that relied on it silently failed. This centralizes the guard and the error
// toast so a copy that can't happen surfaces an error instead of doing nothing.
//
// Usage:
//   const clipboard = useClipboard();
//   await clipboard.copy(token, { successMessage: t("settings.client-token-copied") });
import { useI18n } from "vue-i18n";
import { useSnackbar } from "@/v2/composables/useSnackbar";

export interface CopyOptions {
  /** Success toast message. If omitted, no success toast is shown. */
  successMessage?: string;
  /** Icon for the success toast. Defaults to "mdi-check-bold". */
  successIcon?: string;
  /** Override the error toast shown for either failure. */
  errorMessage?: string;
}

export interface UseClipboard {
  /** True when navigator.clipboard exists AND window.isSecureContext. */
  isSupported: boolean;
  /**
   * Copies `text` to the clipboard. Shows the optional success toast and
   * returns true on success; shows an error toast and returns false when the
   * clipboard is unavailable (non-secure context) or the write throws.
   */
  copy: (text: string, opts?: CopyOptions) => Promise<boolean>;
}

export function useClipboard(): UseClipboard {
  const { t } = useI18n();
  const snackbar = useSnackbar();

  const isSupported =
    typeof navigator !== "undefined" &&
    !!navigator.clipboard &&
    typeof window !== "undefined" &&
    window.isSecureContext;

  async function copy(text: string, opts: CopyOptions = {}): Promise<boolean> {
    const fail = (defaultKey: string) => {
      snackbar.error(opts.errorMessage ?? t(defaultKey), {
        icon: "mdi-close-circle",
      });
      return false;
    };

    if (!isSupported) return fail("common.clipboard-copy-failed");

    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Denied permission or lost focus: HTTPS is already there, so the
      // secure-connection hint would mislead.
      return fail("common.clipboard-write-failed");
    }

    if (opts.successMessage) {
      snackbar.success(opts.successMessage, {
        icon: opts.successIcon ?? "mdi-check-bold",
      });
    }
    return true;
  }

  return { isSupported, copy };
}
