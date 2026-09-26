import { describe, expect, it, vi } from "vitest";
import { reactive } from "vue";
import { useVersionDisplay } from "./index";

function makeHeartbeatStore(system: {
  VERSION: string;
  GIT_BRANCH: string | null;
}) {
  return reactive({ value: { SYSTEM: system } });
}

let heartbeatStore = makeHeartbeatStore({ VERSION: "0.0.0", GIT_BRANCH: null });

vi.mock("@/stores/heartbeat", () => ({ default: () => heartbeatStore }));

describe("useVersionDisplay", () => {
  it("shows the release tag and its GitHub releases link for a tagged build", () => {
    heartbeatStore = makeHeartbeatStore({ VERSION: "4.5.0", GIT_BRANCH: null });
    const { version, href } = useVersionDisplay();
    expect(version.value).toBe("4.5.0");
    expect(href.value).toBe(
      "https://github.com/rommapp/romm/releases/tag/4.5.0",
    );
  });

  it("falls back to the bare 'development' tag when no branch is known", () => {
    heartbeatStore = makeHeartbeatStore({
      VERSION: "development",
      GIT_BRANCH: null,
    });
    const { version, href } = useVersionDisplay();
    expect(version.value).toBe("development");
    expect(href.value).toBe(
      "https://github.com/rommapp/romm/releases/tag/development",
    );
  });

  it("shows the branch and its GitHub tree link on a dev build, preserving '/' as a path separator", () => {
    heartbeatStore = makeHeartbeatStore({
      VERSION: "development",
      GIT_BRANCH: "feature/foo",
    });
    const { version, href } = useVersionDisplay();
    expect(version.value).toBe("feature/foo");
    expect(href.value).toBe("https://github.com/rommapp/romm/tree/feature/foo");
  });

  it("ignores GIT_BRANCH on a tagged build even if the backend sent one", () => {
    heartbeatStore = makeHeartbeatStore({
      VERSION: "4.5.0",
      GIT_BRANCH: "feature/foo",
    });
    const { version, href } = useVersionDisplay();
    expect(version.value).toBe("4.5.0");
    expect(href.value).toBe(
      "https://github.com/rommapp/romm/releases/tag/4.5.0",
    );
  });

  it("links a nightly build to the commit it was built from", () => {
    heartbeatStore = makeHeartbeatStore({
      VERSION: "nightly-a1b2c3d",
      GIT_BRANCH: null,
    });
    const { version, href } = useVersionDisplay();
    expect(version.value).toBe("nightly-a1b2c3d");
    expect(href.value).toBe("https://github.com/rommapp/romm/commit/a1b2c3d");
  });

  it("encodes URL-reserved characters within a branch segment", () => {
    heartbeatStore = makeHeartbeatStore({
      VERSION: "development",
      GIT_BRANCH: "fix/#123-crash",
    });
    const { href } = useVersionDisplay();
    expect(href.value).toBe(
      "https://github.com/rommapp/romm/tree/fix/%23123-crash",
    );
  });
});
