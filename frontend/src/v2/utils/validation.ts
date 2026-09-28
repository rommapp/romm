// Validation helpers for v2 forms. Each export returns a Vuetify-compatible
// rule function: (value) => true | string. Error messages come from i18n
// — utility code is allowed to call i18n.global directly (the
// "primitives must not call $t" rule applies to lib components, not utils).
//
// Usage:
//   import { required, email } from "@/v2/utils/validation";
//   const rules = [required(), email];
//
// Composable rules accept an optional message override:
//   required(t("settings.repeat-password-required"))
import i18n from "@/locales";

type Rule = (v: string | number | null | undefined) => true | string;

const t = (key: string) => i18n.global.t(key);

function isEmpty(v: unknown): boolean {
  if (v == null) return true;
  if (typeof v === "string") return v.length === 0;
  return false;
}

export function required(msg?: string): Rule {
  return (v) => !isEmpty(v) || (msg ?? t("common.required"));
}

/** `required` that also rejects whitespace-only text. */
export function notBlank(msg?: string): Rule {
  return (v) =>
    (typeof v === "string" ? v.trim().length > 0 : !isEmpty(v)) ||
    (msg ?? t("common.required"));
}

export const email: Rule = (v) =>
  typeof v === "string" && /.+@.+\..+/.test(v)
    ? true
    : t("common.invalid-email");

// eslint-disable-next-line no-control-regex
const asciiPattern = /^[\x00-\x7f]*$/;
export const asciiOnly: Rule = (v) =>
  typeof v !== "string" || asciiPattern.test(v) || t("common.ascii-only");

export function lengthBetween(min: number, max: number, msgKey?: string): Rule {
  return (v) => {
    const len = typeof v === "string" ? v.length : 0;
    return (len >= min && len <= max) || t(msgKey ?? "common.length-range");
  };
}

export const usernameLength = lengthBetween(3, 255, "common.username-length");
export const passwordLength = lengthBetween(6, 255, "common.password-length");

const usernameCharsPattern = /^[a-zA-Z0-9_-]*$/;
export const usernameChars: Rule = (v) =>
  typeof v !== "string" ||
  usernameCharsPattern.test(v) ||
  t("common.username-chars");

// Folder path relative to a ROM folder: forward slashes only, no leading
// slash and no empty, "." or ".." segments. Trailing slashes are ignored.
const relativeFolderPattern =
  /^(?!\/)(?!.*\\)(?:(?!\.{1,2}(?:\/|$))[^/]+)(?:\/(?!\.{1,2}(?:\/|$))[^/]+)*$/;
export const relativeFolderPath: Rule = (v) =>
  typeof v === "string" &&
  relativeFolderPattern.test(v.trim().replace(/\/+$/, ""))
    ? true
    : t("common.invalid-relative-path");
