import { useLocalStorage } from "@vueuse/core";
import { computed } from "vue";
import type { BoxartStyleOption } from "@/components/Settings/UserInterface/Interface.vue";
import storeRoms from "@/stores/roms";
import type { SimpleRom, SearchRom } from "@/stores/roms";
import { isCDBasedSystem } from "@/utils";

export const ANIMATION_DELAY = 500;

export function useGameAnimation(
  rom: SimpleRom | SearchRom,
  coverSrc?: string,
) {
  const romsStore = storeRoms();
  const boxartStyle = useLocalStorage<BoxartStyleOption>(
    "settings.boxartStyle",
    "cover",
  );

  // User selected alternative cover image
  const boxartStyleCover = computed(() => {
    if (
      coverSrc ||
      !romsStore.isSimpleRom(rom) ||
      boxartStyle.value === "cover"
    )
      return null;
    const ssMedia = rom.ss_metadata?.[boxartStyle.value];
    const gamelistMedia = rom.gamelist_metadata?.[boxartStyle.value];
    return ssMedia || gamelistMedia;
  });

  const animateCD = computed(() => {
    return (
      boxartStyle.value === "physical_path" &&
      Boolean(boxartStyleCover.value) &&
      romsStore.isSimpleRom(rom) &&
      isCDBasedSystem(rom.platform_slug)
    );
  });

  const animateCartridge = computed(() => {
    return (
      boxartStyle.value === "physical_path" &&
      Boolean(boxartStyleCover.value) &&
      romsStore.isSimpleRom(rom) &&
      !isCDBasedSystem(rom.platform_slug)
    );
  });

  return {
    boxartStyleCover,
    animateCD,
    animateCartridge,
  };
}
