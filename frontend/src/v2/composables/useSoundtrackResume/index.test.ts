import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, ref } from "vue";
import storeAuth from "@/stores/auth";
import useSoundtrackPlayer, {
  type SoundtrackSession,
} from "@/stores/soundtrackPlayer";
import type { User } from "@/stores/users";
import {
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
  storeAuth().setCurrentUser({ id } as User);
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

  it.each(["not json", "null", JSON.stringify({ userId: 1, session: {} })])(
    "fails safe on %s",
    (raw) => {
      expect(readStoredSession(raw)).toBeNull();
    },
  );
});

describe("useSoundtrackResume", () => {
  it("restores the signed-in user's session", async () => {
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 1, session }),
    );
    signIn(1);
    mountResume();
    await nextTick();

    expect(useSoundtrackPlayer().track).toEqual(track);
  });

  it("waits for the user before restoring", async () => {
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 1, session }),
    );
    mountResume();
    await nextTick();
    expect(useSoundtrackPlayer().track).toBeNull();

    signIn(1);
    await nextTick();
    expect(useSoundtrackPlayer().track).toEqual(track);
  });

  it("never restores another user's session", async () => {
    localStorage.setItem(
      SOUNDTRACK_SESSION_KEY,
      JSON.stringify({ userId: 2, session }),
    );
    signIn(1);
    mountResume();
    await nextTick();

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
    await nextTick();

    expect(useSoundtrackPlayer().track).toBeNull();
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
    await nextTick();

    expect(localStorage.getItem(SOUNDTRACK_SESSION_KEY)).toBeNull();
  });
});
