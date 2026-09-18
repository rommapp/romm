// The version to display and where it should link. Shows the branch on a
// dev build, when known, instead of the bare "development" placeholder.
import { computed } from "vue";
import storeHeartbeat from "@/stores/heartbeat";

export function useVersionDisplay() {
  const heartbeatStore = storeHeartbeat();

  const branch = computed(() => {
    const { VERSION, GIT_BRANCH } = heartbeatStore.value.SYSTEM;
    return VERSION === "development" ? GIT_BRANCH : null;
  });

  const version = computed(
    () => branch.value ?? heartbeatStore.value.SYSTEM.VERSION,
  );

  const href = computed(() => {
    // Branch names commonly contain "/" (e.g. "feature/foo"), which GitHub
    // expects as literal path separators, so encode each segment on its own.
    const encodedBranch = branch.value
      ?.split("/")
      .map(encodeURIComponent)
      .join("/");
    return encodedBranch
      ? `https://github.com/rommapp/romm/tree/${encodedBranch}`
      : `https://github.com/rommapp/romm/releases/tag/${heartbeatStore.value.SYSTEM.VERSION}`;
  });

  return { version, href };
}
