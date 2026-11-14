import { useI18n } from "vue-i18n";
import type { DeviceRefSchema } from "@/__generated__";

/** How a snapshot's device reads to this viewer: another user's is never named. */
export function useDeviceLabel() {
  const { t } = useI18n();
  return (device: DeviceRefSchema | null) => {
    if (!device) return t("channels.no-device");
    if (!device.is_own) return t("channels.other-device");
    return device.name ?? device.client ?? t("channels.no-device");
  };
}
