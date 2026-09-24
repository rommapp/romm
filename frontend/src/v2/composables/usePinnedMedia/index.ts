// usePinnedMedia: read and toggle what the Overview tab shows for one ROM.
// Writes are optimistic and chained, so rapid toggles reach the server in
// click order and the last one wins.
import { computed, toValue, type MaybeRefOrGetter } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import { pinnedMediaKeys, togglePinnedMediaKey } from "@/v2/utils/pinnedMedia";

export function usePinnedMedia(rom: MaybeRefOrGetter<DetailedRom>) {
  const { t } = useI18n();
  const snackbar = useSnackbar();

  const pinned = computed(() => new Set(pinnedMediaKeys(toValue(rom))));
  const isCustomized = computed(
    () => toValue(rom).rom_user?.pinned_media != null,
  );

  let queue = Promise.resolve();

  function write(next: string[] | null) {
    const target = toValue(rom);
    const romUser = target.rom_user;
    if (!romUser) return;

    const before = romUser.pinned_media;
    romUser.pinned_media = next;
    queue = queue.then(async () => {
      try {
        await romApi.updateUserRomProps({
          romId: target.id,
          data: { pinned_media: next },
        });
      } catch {
        romUser.pinned_media = before;
        snackbar.error(t("rom.pinned-media-update-failed"), {
          icon: "mdi-alert-circle-outline",
        });
      }
    });
  }

  function isPinned(key: string): boolean {
    return pinned.value.has(key);
  }

  function togglePin(key: string) {
    write(togglePinnedMediaKey(pinnedMediaKeys(toValue(rom)), key));
  }

  function resetPins() {
    write(null);
  }

  return { isPinned, isCustomized, togglePin, resetPins };
}
