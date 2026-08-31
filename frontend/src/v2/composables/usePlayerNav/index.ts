// usePlayerNav — the two back links every v2 player view carries. The route id
// is used rather than the hero's, so the links work during the seed window.
import { useRouter } from "vue-router";
import { ROUTES } from "@/plugins/router";

export function usePlayerNav(
  romId: number,
  platformId: () => number | null | undefined,
): {
  backToRom: () => void;
  backToPlatform: () => void;
} {
  const router = useRouter();

  function backToRom() {
    router.push({ name: ROUTES.ROM, params: { rom: romId } });
  }

  function backToPlatform() {
    const platform = platformId();
    if (platform == null) return;
    router.push({ name: ROUTES.PLATFORM, params: { platform } });
  }

  return { backToRom, backToPlatform };
}
