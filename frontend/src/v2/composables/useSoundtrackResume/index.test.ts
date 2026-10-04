import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, onTestFinished, vi } from "vitest";
import { defineComponent, ref } from "vue";
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

function signIn(id: number) {
  storeAuth().setCurrentUser(userFixture({ id }));
}

function mountResume() {
  return mount(
    defineComponent({ setup: useSoundtrackResume, render: () => null }),
  );
}

function stored() {
  const raw = localStorage.getItem(SOUNDTRACK_SESSION_KEY);
  return raw === null ? null : readStoredSession(raw);
}

beforeEach(() => {
  localStorage.clear();
  resumeMusic.value = true;
});

describe("readStoredSession", () => {
  it("reads a saved session", () => {
    const raw = JSON.stringify({ userId: 1, session });
    expect(readStoredSession(raw)).toEqual({ userId: 1, session });
  });

  it.each([
    "not json",
    "null",
    JSON.stringify({ userId: 1, session: {} }),
    JSON.stringify({ userId: 1, session: { ...session, meta: undefined } }),
    JSON.stringify({ userId: 1, session: { ...session, playlist: [{}] } }),
    JSON.stringify({ userId: 1, session: { ...session, isShuffled: "no" } }),
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
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 1, session }),
    );
    signIn(1);
    mountResume();
    await settle();

    expect(useSoundtrackPlayer().track).toEqual(track);
  });

  it("autoplays a session no other tab is playing", async () => {
    otherTab(false);
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 1, session }),
    );
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
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 1, session }),
    );
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
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 1, session }),
    );
    mountResume();
    await settle();
    expect(useSoundtrackPlayer().track).toBeNull();

    signIn(1);
    await settle();
    expect(useSoundtrackPlayer().track).toEqual(track);
  });

  it("never restores another user's session", async () => {
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 2, session }),
    );
    signIn(1);
    mountResume();
    await settle();

    expect(useSoundtrackPlayer().track).toBeNull();
  });

  it("restores nothing while the setting is off", async () => {
    resumeMusic.value = false;
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 1, session }),
    );
    signIn(1);
    mountResume();
    await settle();

    expect(useSoundtrackPlayer().track).toBeNull();
  });

  it("restores the next user's session after a sign-out", async () => {
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 2, session: { ...session, track: other } }),
    );
    signIn(1);
    mountResume();
    const player = useSoundtrackPlayer();
    player.play(track, {});

    player.reset();
    storeAuth().reset();
    await settle();
    signIn(2);
    await settle();

    expect(player.track).toEqual(other);
    window.dispatchEvent(new Event("pagehide"));
    expect(stored()?.userId).toBe(2);
    expect(stored()?.session.track).toEqual(other);
  });

  it("saves the session when the page is hidden", () => {
    signIn(1);
    mountResume();
    useSoundtrackPlayer().play(track, {});

    window.dispatchEvent(new Event("pagehide"));

    expect(stored()).toEqual({
      userId: 1,
      session: {
        ...session,
        playlist: [],
        originalPlaylist: [],
        position: 0,
        wasPlaying: false,
      },
    });
  });

  it("forgets the saved session when the setting is turned off", async () => {
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 1, session }),
    );
    signIn(1);
    mountResume();

    resumeMusic.value = false;
    await settle();

    expect(localStorage.getItem(SOUNDTRACK_SESSION_KEY)).toBeNull();
  });
});
