import { ref } from "vue";
import { useConsoleTheme } from "@/stores/consoleTheme";
import type { SimpleRom } from "@/stores/roms";

const selectedGame = ref<SimpleRom | null>(null);

export function useSelectedGameBackground() {
  const consoleTheme = useConsoleTheme();
  const setSelectedGame = (rom: SimpleRom) => {
    selectedGame.value = rom;
    const coverSrc =
      rom.path_cover_large || rom.path_cover_small || rom.url_cover || "";
    if (coverSrc) {
      document.documentElement.style.setProperty(
        "--theme-background",
        `url("${coverSrc}")`,
      );
    }
  };

  const clearSelectedGame = () => {
    selectedGame.value = null;
    consoleTheme.updateBackgroundCSS();
  };

  return {
    setSelectedGame,
    clearSelectedGame,
    selectedGame,
  };
}
