// useVersionDisplay — the running RomM version to display, and where it
// should link. A local checkout has no release tag, so shows the branch
// being worked on instead of the bare "development" placeholder when one
// is known.
import { computed } from "vue";
import storeHeartbeat from "@/stores/heartbeat";

export function useVersionDisplay() {
  const heartbeatStore = storeHeartbeat();

  const isDevBuild = computed(
    () => heartbeatStore.value.SYSTEM.VERSION === "development",
  );

  const version = computed(() => {
    const { VERSION, GIT_BRANCH } = heartbeatStore.value.SYSTEM;
    return isDevBuild.value && GIT_BRANCH ? GIT_BRANCH : VERSION;
  });

  const href = computed(() => {
    const { VERSION, GIT_BRANCH } = heartbeatStore.value.SYSTEM;
    return isDevBuild.value && GIT_BRANCH
      ? `https://github.com/rommapp/romm/tree/${GIT_BRANCH}`
      : `https://github.com/rommapp/romm/releases/tag/${VERSION}`;
  });

  return { version, href };
}
