import { mount } from "@vue/test-utils";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  onTestFinished,
  vi,
} from "vitest";
import { defineComponent, ref } from "vue";
import { setStorageUser } from "@/composables/useUserLocalStorage";
import storeAuth from "@/stores/auth";
import useSoundtrackPlayer, {
  type SoundtrackSession,
} from "@/stores/soundtrackPlayer";
import { userFixture } from "@/utils/user.fixtures";
import {
  PLAYING_REPLY_TIMEOUT_MS,
  SOUNDTRACK_CHANNEL,
  SOUNDTRACK_SESSION_KEY,
  readStoredSession,
  useSoundtrackResume,
} from ".";

const resumeMusic = ref(true);
vi.mock("@/composables/useUISettings", () => ({
  useUISettings: () => ({ resumeMusic }),
}));

const track = {
  romId: 1,
  fileId: 2,
  fileName: "02 Theme.mp3",
  url: "/theme.mp3",
};
const other = {
  ...track,
  fileId: 3,
  fileName: "03 Boss.mp3",
  url: "/boss.mp3",
};
const session: SoundtrackSession = {
  track,
  meta: {},
  playlist: [track],
  originalPlaylist: [track],
  isShuffled: false,
  playlistMeta: {},
  activePlaylistRomId: null,
  position: 42,
  wasPlaying: true,
};

// Storage follows the user first, as main.ts wires it.
function signIn(id: number) {
  setStorageUser(id);
  storeAuth().setCurrentUser(userFixture({ id }));
}

function signOut() {
  setStorageUser(null);
  storeAuth().reset();
}

function keyFor(userId: number) {
  return `user:${userId}:${SOUNDTRACK_SESSION_KEY}`;
}

function seed(userId: number, saved: SoundtrackSession) {
  localStorage.setItem(keyFor(userId), JSON.stringify(saved));
}

function mountResume() {
  return mount(
    defineComponent({ setup: useSoundtrackResume, render: () => null }),
  );
}

function stored(userId: number) {
  const raw = localStorage.getItem(keyFor(userId));
  return raw === null ? null : readStoredSession(raw);
}

beforeEach(() => {
  localStorage.clear();
  setStorageUser(null);
  resumeMusic.value = true;
});

afterEach(() => {
  setStorageUser(null);
});

describe("readStoredSession", () => {
  it("reads a saved session", () => {
    expect(readStoredSession(JSON.stringify(session))).toEqual(session);
  });

  it.each([
    "not json",
    "null",
    JSON.stringify({}),
    JSON.stringify({ ...session, meta: undefined }),
    JSON.stringify({ ...session, playlist: [{}] }),
    JSON.stringify({ ...session, isShuffled: "no" }),
  ])("fails safe on %s", (raw) => {
    expect(readStoredSession(raw)).toBeNull();
  });
});

describe("useSoundtrackResume", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  // Lets the restore's "is another tab playing?" question go unanswered.
  async function settle() {
    await vi.advanceTimersByTimeAsync(PLAYING_REPLY_TIMEOUT_MS);
  }

  // Stands in for another open tab on the same channel.
  function otherTab(playing: boolean) {
    const channel = new BroadcastChannel(SOUNDTRACK_CHANNEL);
    const heard: unknown[] = [];
    channel.onmessage = (event: MessageEvent) => {
      heard.push(event.data);
      if (event.data === "ask" && playing) channel.postMessage("playing");
    };
    onTestFinished(() => channel.close());
    return { channel, heard };
  }

  it("restores the signed-in user's session", async () => {
    seed(1, session);
    signIn(1);
    mountResume();
    await settle();

    expect(useSoundtrackPlayer().track).toEqual(track);
  });

  it("autoplays a session no other tab is playing", async () => {
    otherTab(false);
    seed(1, session);
    signIn(1);
    mountResume();
    await settle();

    expect(useSoundtrackPlayer().pendingResume).toEqual({
      position: 42,
      autoplay: true,
    });
  });

  it("loads paused while another tab is playing", async () => {
    otherTab(true);
    seed(1, session);
    signIn(1);
    mountResume();

    await vi.waitFor(() =>
      expect(useSoundtrackPlayer().pendingResume).toEqual({
        position: 42,
        autoplay: false,
      }),
    );
  });

  it("tells other tabs when it is playing", async () => {
    const { channel, heard } = otherTab(false);
    signIn(1);
    mountResume();
    const player = useSoundtrackPlayer();
    player.play(track, {});
    player.setPlaying(true);

    channel.postMessage("ask");

    await vi.waitFor(() => expect(heard).toContain("playing"));
  });

  it("waits for the user before restoring", async () => {
    seed(1, session);
    mountResume();
    await settle();
    expect(useSoundtrackPlayer().track).toBeNull();

    signIn(1);
    await settle();
    expect(useSoundtrackPlayer().track).toEqual(track);
  });

  it("never restores another user's session", async () => {
    seed(2, session);
    signIn(1);
    mountResume();
    await settle();

    expect(useSoundtrackPlayer().track).toBeNull();
  });

  it("restores nothing while the setting is off", async () => {
    resumeMusic.value = false;
    seed(1, session);
    signIn(1);
    mountResume();
    await settle();

    expect(useSoundtrackPlayer().track).toBeNull();
  });

  it("restores the next user's session after a sign-out", async () => {
    seed(2, { ...session, track: other });
    signIn(1);
    mountResume();
    const player = useSoundtrackPlayer();
    player.play(track, {});

    player.reset();
    signOut();
    await settle();
    signIn(2);
    await settle();

    expect(player.track).toEqual(other);
    window.dispatchEvent(new Event("pagehide"));
    expect(stored(2)?.track).toEqual(other);
  });

  it("saves the session when the page is hidden", () => {
    signIn(1);
    mountResume();
    useSoundtrackPlayer().play(track, {});

    window.dispatchEvent(new Event("pagehide"));

    expect(stored(1)).toEqual({
      ...session,
      playlist: [],
      originalPlaylist: [],
      position: 0,
      wasPlaying: false,
    });
  });

  it("leaves the saved session alone while a restored one hasn't started", async () => {
    seed(1, session);
    signIn(1);
    mountResume();
    await settle();
    const fromOtherTab = { ...session, track: other };
    seed(1, fromOtherTab);

    await vi.advanceTimersByTimeAsync(5000);
    window.dispatchEvent(new Event("pagehide"));

    expect(stored(1)).toEqual(fromOtherTab);
  });

  it("doesn't save over another tab once its own changes are saved", () => {
    signIn(1);
    mountResume();
    useSoundtrackPlayer().play(track, {});
    window.dispatchEvent(new Event("pagehide"));
    const fromOtherTab = { ...session, track: other };
    seed(1, fromOtherTab);

    window.dispatchEvent(new Event("pagehide"));

    expect(stored(1)).toEqual(fromOtherTab);
  });

  it("forgets the saved session when the setting is turned off", async () => {
    seed(1, session);
    signIn(1);
    mountResume();

    resumeMusic.value = false;
    await settle();

    expect(localStorage.getItem(keyFor(1))).toBeNull();
  });
});
