// The version to display and where it should link. Shows the branch on a
// dev build, when known, instead of the bare "development" placeholder, and
// links an edge build (`edge-<short sha>`, built from master) to its commit.
import { computed } from "vue";
import storeHeartbeat from "@/stores/heartbeat";

const EDGE_VERSION_RE = /^edge-([0-9a-f]{7,40})$/;

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
    if (encodedBranch) {
      return `https://github.com/rommapp/romm/tree/${encodedBranch}`;
    }
    const edgeCommit = EDGE_VERSION_RE.exec(version.value)?.[1];
    return edgeCommit
      ? `https://github.com/rommapp/romm/commit/${edgeCommit}`
      : `https://github.com/rommapp/romm/releases/tag/${version.value}`;
  });

  return { version, href };
}
