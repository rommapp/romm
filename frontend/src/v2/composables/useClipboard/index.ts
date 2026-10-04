// The Clipboard API needs a secure context, so plain HTTP falls back to
// `execCommand("copy")`; a copy that still fails shows an error toast.
//
// Usage:
//   const clipboard = useClipboard();
//   await clipboard.copy(token, { successMessage: t("settings.client-token-copied") });
import { useI18n } from "vue-i18n";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { focusFromInput } from "@/v2/utils/autofocus";

export interface CopyOptions {
  /** Success toast message. If omitted, no success toast is shown. */
  successMessage?: string;
  /** Icon for the success toast. Defaults to "mdi-check-bold". */
  successIcon?: string;
  /** Override the error toast shown for either failure. */
  errorMessage?: string;
  /** Called instead of the error toast on either failure, e.g. to show the text for a manual copy. */
  fallback?: () => void;
}

export interface UseClipboard {
  /** True when either the Clipboard API or the `execCommand` fallback exists. */
  isSupported: boolean;
  /**
   * Copies `text` to the clipboard. Shows the optional success toast and
   * returns true on success; shows an error toast (or runs `fallback`) and
   * returns false when neither the Clipboard API nor the fallback copies.
   */
  copy: (text: string, opts?: CopyOptions) => Promise<boolean>;
}

function legacyCopy(text: string): boolean {
  const previous = document.activeElement as HTMLElement | null;
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.top = "0";
  area.style.opacity = "0";
  document.body.appendChild(area);
  focusFromInput(area, { preventScroll: true });
  area.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch {
    // Some browsers throw instead of returning false.
  }
  area.remove();
  // Spatial and grid nav track focus, so hand it back to the trigger.
  focusFromInput(previous, { preventScroll: true });
  return ok;
}

export function useClipboard(): UseClipboard {
  const { t } = useI18n();
  const snackbar = useSnackbar();

  const hasClipboardApi =
    typeof navigator !== "undefined" &&
    !!navigator.clipboard &&
    typeof window !== "undefined" &&
    window.isSecureContext;
  const hasLegacyCopy =
    typeof document !== "undefined" &&
    typeof document.execCommand === "function";
  const isSupported = hasClipboardApi || hasLegacyCopy;

  async function copy(text: string, opts: CopyOptions = {}): Promise<boolean> {
    const fail = (defaultKey: string) => {
      if (opts.fallback) {
        opts.fallback();
        return false;
      }
      snackbar.error(opts.errorMessage ?? t(defaultKey), {
        icon: "mdi-close-circle",
      });
      return false;
    };

    let copied = false;
    if (hasClipboardApi) {
      try {
        await navigator.clipboard.writeText(text);
        copied = true;
      } catch {
        // Denied permission or lost focus; the fallback may still succeed.
      }
    }
    if (!copied && hasLegacyCopy) copied = legacyCopy(text);
    if (!copied) {
      // With HTTPS already in place, the secure-connection hint would mislead.
      return fail(
        hasClipboardApi
          ? "common.clipboard-write-failed"
          : "common.clipboard-copy-failed",
      );
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
