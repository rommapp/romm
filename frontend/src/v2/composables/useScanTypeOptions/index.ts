import { computed, type ComputedRef } from "vue";
import { useI18n } from "vue-i18n";
import type { ScanTypeOption } from "@/v2/types/scan";

export function useScanTypeOptions(): ComputedRef<ScanTypeOption[]> {
  const { t } = useI18n();
  return computed(() => [
    {
      title: t("scan.new-platforms"),
      subtitle: t("scan.new-platforms-desc"),
      value: "new_platforms",
    },
    {
      title: t("scan.quick-scan"),
      subtitle: t("scan.quick-scan-desc"),
      value: "quick",
    },
    {
      title: t("scan.unmatched-games"),
      subtitle: t("scan.unmatched-games-desc"),
      value: "unmatched",
    },
    {
      title: t("scan.update-metadata"),
      subtitle: t("scan.update-metadata-desc"),
      value: "update",
    },
    {
      title: t("scan.hashes"),
      subtitle: t("scan.hashes-desc"),
      value: "hashes",
    },
    {
      title: t("scan.complete-rescan"),
      subtitle: t("scan.complete-rescan-desc"),
      value: "complete",
    },
  ]);
}
