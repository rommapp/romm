import { useLocalStorage } from "@vueuse/core";
import { debounce } from "lodash";
import { ref } from "vue";
import { resolveAsset } from "../utils/assetResolver";

const currentLayer = ref<"background" | "foreground">("background");

export default function useBackgroundArt() {
  const themeName = useLocalStorage("console.theme", "default");

  const _updateDocumentCSS = (url: string) => {
    if (currentLayer.value === "background") {
      document.documentElement.style.setProperty(
        "--console-root-foreground",
        `url("${url}")`,
      );
      document.documentElement.style.setProperty("--console-root-opacity", "1");
      currentLayer.value = "foreground";
    } else {
      document.documentElement.style.setProperty(
        "--console-root-background",
        `url("${url}")`,
      );
      document.documentElement.style.setProperty("--console-root-opacity", "0");
      currentLayer.value = "background";
    }
  };

  const debouncedUpdateDocumentCSS = debounce(_updateDocumentCSS, 300);

  const setSelectedBackgroundArt = (url: string) => {
    if (!url) return;
    debouncedUpdateDocumentCSS(url);
  };

  const clearSelectedBackgroundArt = () => {
    const backgroundPath = resolveAsset(
      "backgrounds",
      "background",
      "svg",
      themeName.value,
    );
    debouncedUpdateDocumentCSS(backgroundPath);
  };

  return {
    setSelectedBackgroundArt,
    clearSelectedBackgroundArt,
  };
}
