import { ref } from "vue";
import { useConsoleTheme } from "@/stores/consoleTheme";

const selectedBackgroundArt = ref<string | null>(null);

export default function useBackgroundArt() {
  const consoleTheme = useConsoleTheme();
  const setSelectedBackgroundArt = (url: string) => {
    selectedBackgroundArt.value = url;
    if (url) {
      document.documentElement.style.setProperty(
        "--theme-background",
        `url("${url}")`,
      );
    }
  };

  const clearSelectedBackgroundArt = () => {
    selectedBackgroundArt.value = null;
    consoleTheme.updateBackgroundCSS();
  };

  return {
    setSelectedBackgroundArt,
    clearSelectedBackgroundArt,
    selectedBackgroundArt,
  };
}
