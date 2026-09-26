// usePinnedMedia: read and toggle what the Overview tab shows for one ROM.
// Writes are optimistic and chained per ROM across every caller, so rapid
// toggles reach the server in click order and the last one wins.
import { computed, toValue, type MaybeRefOrGetter } from "vue";
import { useI18n } from "vue-i18n";
import romApi from "@/services/api/rom";
import type { DetailedRom } from "@/stores/roms";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import {
  PINNED_MEDIA_MAX_ITEMS,
  pinnedMediaKeys,
  togglePinnedMediaKey,
} from "@/v2/utils/pinnedMedia";

type RomWrites = {
  queue: Promise<void>;
  pending: number;
  confirmed: string[] | null;
};

// The Overview, Screenshots and Artwork tabs each hold an instance, so the
// queue lives at module scope, keyed by ROM id.
const romWrites = new Map<number, RomWrites>();

export function usePinnedMedia(rom: MaybeRefOrGetter<DetailedRom>) {
  const { t } = useI18n();
  const snackbar = useSnackbar();

  const pinned = computed(() => new Set(pinnedMediaKeys(toValue(rom))));
  const isCustomized = computed(
    () => toValue(rom).rom_user?.pinned_media != null,
  );

  function write(next: string[] | null) {
    const target = toValue(rom);
    const romUser = target.rom_user;
    if (!romUser) return;

    let writes = romWrites.get(target.id);
    if (!writes) {
      writes = {
        queue: Promise.resolve(),
        pending: 0,
        confirmed: romUser.pinned_media,
      };
      romWrites.set(target.id, writes);
    }
    const state = writes;
    romUser.pinned_media = next;
    state.pending++;
    state.queue = state.queue.then(async () => {
      try {
        await romApi.updateUserRomProps({
          romId: target.id,
          data: { pinned_media: next },
        });
        state.confirmed = next;
      } catch {
        // A newer queued write already carries the state the user wants.
        if (state.pending === 1) romUser.pinned_media = state.confirmed;
        snackbar.error(t("rom.pinned-media-update-failed"), {
          icon: "mdi-alert-circle-outline",
        });
      } finally {
        if (--state.pending === 0) romWrites.delete(target.id);
      }
    });
  }

  function isPinned(key: string): boolean {
    return pinned.value.has(key);
  }

  function togglePin(key: string) {
    const next = togglePinnedMediaKey(pinnedMediaKeys(toValue(rom)), key);
    if (next.length > PINNED_MEDIA_MAX_ITEMS) {
      snackbar.error(
        t("rom.pinned-media-limit", { n: PINNED_MEDIA_MAX_ITEMS }),
        { icon: "mdi-alert-circle-outline" },
      );
      return;
    }
    write(next);
  }

  function resetPins() {
    write(null);
  }

  return { isPinned, isCustomized, togglePin, resetPins };
}
