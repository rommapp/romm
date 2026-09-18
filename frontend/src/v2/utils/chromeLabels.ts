// Translated backing for the v2 library's chrome labels (see
// `@/v2/lib/a11y/chromeLabels`). Primitives may not touch i18n, so the app
// builds the bundle here and provides it once.
//
// Each property is a getter, so `t` runs inside the reading component's
// render effect and a locale switch re-renders the labels. Utility code is
// allowed to call i18n.global directly, as `validation.ts` does.
import i18n from "@/locales";
import type { ChromeLabels } from "@/v2/lib/a11y/chromeLabels";

const t = (key: string) => i18n.global.t(key);

export function createChromeLabels(): ChromeLabels {
  return {
    get close() {
      return t("common.close");
    },
    get clear() {
      return t("common.clear");
    },
    get remove() {
      return t("common.remove");
    },
    get all() {
      return t("common.all");
    },
    get previous() {
      return t("common.previous");
    },
    get next() {
      return t("common.next");
    },
    get datePicker() {
      return t("common.date-picker");
    },
    get previousYear() {
      return t("common.previous-year");
    },
    get previousMonth() {
      return t("common.previous-month");
    },
    get nextMonth() {
      return t("common.next-month");
    },
    get nextYear() {
      return t("common.next-year");
    },
    get today() {
      return t("common.today");
    },
  };
}
