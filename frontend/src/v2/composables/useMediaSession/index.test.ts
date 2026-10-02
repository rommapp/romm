import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, type EffectScope } from "vue";
import useSoundtrackPlayer, {
  type PlayerMeta,
  type PlayerTrack,
} from "@/stores/soundtrackPlayer";
import { useMediaSession } from "@/v2/composables/useMediaSession";

class FakeMediaMetadata {
  title: string;
  artist: string;
  album: string;
  artwork: MediaImage[];

  constructor(init: MediaMetadataInit = {}) {
    this.title = init.title ?? "";
    this.artist = init.artist ?? "";
    this.album = init.album ?? "";
    this.artwork = [...(init.artwork ?? [])];
  }
}

class FakeMediaSession {
  metadata: FakeMediaMetadata | null = null;
  playbackState: MediaSessionPlaybackState = "none";
  handlers = new Map<MediaSessionAction, MediaSessionActionHandler>();
  setPositionState = vi.fn<(state?: MediaPositionState) => void>();

  setActionHandler(
    action: MediaSessionAction,
    handler: MediaSessionActionHandler | null,
  ) {
    if (action === "stop" && this.rejectStop) {
      throw new TypeError("unsupported");
    }
    if (handler) this.handlers.set(action, handler);
    else this.handlers.delete(action);
  }

  rejectStop = false;

  fire(
    action: MediaSessionAction,
    details: Partial<MediaSessionActionDetails>,
  ) {
    this.handlers.get(action)?.({ action, ...details });
  }
}

function track(fileId: number): PlayerTrack {
  return {
    romId: 1,
    fileId,
    fileName: `track-${fileId}.mp3`,
    url: `/api/roms/1/files/${fileId}/content/track-${fileId}.mp3`,
  };
}

// A real element whose `paused` and `currentTime` change at once, while its
// events (and so the store) lag behind.
function fakeAudio() {
  const el = document.createElement("audio");
  const state = { paused: true, currentTime: 0 };
  Object.defineProperty(el, "paused", { get: () => state.paused });
  Object.defineProperty(el, "currentTime", {
    get: () => state.currentTime,
    set: (t: number) => {
      state.currentTime = t;
    },
  });
  const play = vi.spyOn(el, "play").mockImplementation(async () => {
    state.paused = false;
  });
  const pause = vi.spyOn(el, "pause").mockImplementation(() => {
    state.paused = true;
  });
  vi.spyOn(el, "load").mockImplementation(() => {});
  return { el, state, play, pause };
}

describe("useMediaSession", () => {
  let session: FakeMediaSession;
  let scope: EffectScope;

  beforeEach(() => {
    session = new FakeMediaSession();
    Object.defineProperty(navigator, "mediaSession", {
      configurable: true,
      value: session,
    });
    vi.stubGlobal("MediaMetadata", FakeMediaMetadata);
    scope = effectScope();
  });

  afterEach(() => {
    scope.stop();
    Reflect.deleteProperty(navigator, "mediaSession");
  });

  function start(blocked?: () => boolean) {
    scope.run(() => useMediaSession(blocked));
  }

  it("sets metadata with the mini player's cover and clears it on stop", async () => {
    const store = useSoundtrackPlayer();
    start();
    expect(session.metadata).toBeNull();
    expect(session.playbackState).toBe("none");

    const meta: PlayerMeta = {
      title: "Green Hill Zone",
      artist: "Masato Nakamura",
      album: "Sonic the Hedgehog",
      gameArtworkUrl: "/assets/romm/resources/roms/1/cover.png",
    };
    store.play(track(1), meta);
    await nextTick();
    expect(session.metadata).toEqual(
      new FakeMediaMetadata({
        title: "Green Hill Zone",
        artist: "Masato Nakamura",
        album: "Sonic the Hedgehog",
        artwork: [{ src: "/assets/romm/resources/roms/1/cover.png" }],
      }),
    );

    store.stop();
    await nextTick();
    expect(session.metadata).toBeNull();
    expect(session.playbackState).toBe("none");
  });

  it("falls back to the file name and default cover without tags", async () => {
    const store = useSoundtrackPlayer();
    start();
    store.play(track(2), {});
    await nextTick();
    expect(session.metadata?.title).toBe("track-2.mp3");
    expect(session.metadata?.artwork).toEqual([
      { src: "/assets/default/album_cover.jpg" },
    ]);
  });

  it("keeps playbackState in sync with the player", async () => {
    const store = useSoundtrackPlayer();
    start();
    store.play(track(1), {});
    await nextTick();
    expect(session.playbackState).toBe("paused");

    store.setPlaying(true);
    await nextTick();
    expect(session.playbackState).toBe("playing");

    store.setPlaying(false);
    await nextTick();
    expect(session.playbackState).toBe("paused");
  });

  it("routes play, pause and stop to the player", () => {
    const store = useSoundtrackPlayer();
    const audio = fakeAudio();
    store.setAudioRef(audio.el);
    const stop = vi.spyOn(store, "stop");
    start();

    session.fire("play", {});
    expect(audio.play).not.toHaveBeenCalled();

    store.play(track(1), {});
    session.fire("pause", {});
    expect(audio.pause).not.toHaveBeenCalled();
    session.fire("play", {});
    expect(audio.play).toHaveBeenCalledTimes(1);
    session.fire("play", {});
    expect(audio.play).toHaveBeenCalledTimes(1);

    session.fire("stop", {});
    expect(stop).toHaveBeenCalledOnce();
  });

  it("follows the element through presses faster than its events", () => {
    const store = useSoundtrackPlayer();
    const audio = fakeAudio();
    audio.state.paused = false;
    store.setAudioRef(audio.el);
    store.play(track(1), {});
    store.setPlaying(true);
    start();

    session.fire("pause", {});
    session.fire("play", {});

    expect(audio.pause).toHaveBeenCalledOnce();
    expect(audio.play).toHaveBeenCalledOnce();
    expect(audio.state.paused).toBe(false);
  });

  it("ignores play while the music is blocked, but still pauses", () => {
    const store = useSoundtrackPlayer();
    const audio = fakeAudio();
    store.setAudioRef(audio.el);
    store.play(track(1), {});
    let blocked = true;
    start(() => blocked);

    session.fire("play", {});
    expect(audio.play).not.toHaveBeenCalled();

    blocked = false;
    session.fire("play", {});
    expect(audio.play).toHaveBeenCalledOnce();

    blocked = true;
    session.fire("pause", {});
    expect(audio.pause).toHaveBeenCalledOnce();
  });

  it("seeks to a time and by an offset within the track", () => {
    const store = useSoundtrackPlayer();
    const seek = vi.spyOn(store, "seek").mockImplementation(() => {});
    start();
    store.play(track(1), {});
    store.setDuration(100);
    store.currentTime = 50;

    session.fire("seekto", { seekTime: 42 });
    expect(seek).toHaveBeenLastCalledWith(42);

    session.fire("seekforward", {});
    expect(seek).toHaveBeenLastCalledWith(60);
    session.fire("seekbackward", { seekOffset: 5 });
    expect(seek).toHaveBeenLastCalledWith(45);

    session.fire("seekforward", { seekOffset: 80 });
    expect(seek).toHaveBeenLastCalledWith(100);
    session.fire("seekbackward", { seekOffset: 80 });
    expect(seek).toHaveBeenLastCalledWith(0);
  });

  it("adds up seek presses that land before the next time update", () => {
    const store = useSoundtrackPlayer();
    const audio = fakeAudio();
    audio.state.currentTime = 50;
    store.setAudioRef(audio.el);
    start();
    store.play(track(1), {});
    store.setDuration(100);
    store.currentTime = 50;

    session.fire("seekforward", {});
    session.fire("seekforward", {});

    expect(audio.state.currentTime).toBe(70);
    expect(store.currentTime).toBe(50);
  });

  it("offers previous and next only when the queue has them", async () => {
    const store = useSoundtrackPlayer();
    const next = vi.spyOn(store, "next");
    const previous = vi.spyOn(store, "previous");
    start();
    expect(session.handlers.has("previoustrack")).toBe(false);
    expect(session.handlers.has("nexttrack")).toBe(false);

    store.loadPlaylist([track(1), track(2)], {});
    store.play(track(1), {});
    await nextTick();
    expect(session.handlers.has("previoustrack")).toBe(false);
    expect(session.handlers.has("nexttrack")).toBe(true);

    session.fire("nexttrack", {});
    expect(next).toHaveBeenCalledOnce();
    await nextTick();
    expect(session.handlers.has("previoustrack")).toBe(true);
    expect(session.handlers.has("nexttrack")).toBe(false);

    session.fire("previoustrack", {});
    expect(previous).toHaveBeenCalledOnce();
  });

  it("clamps the position state and skips unknown durations", async () => {
    const store = useSoundtrackPlayer();
    start();
    store.play(track(1), {});
    await nextTick();
    expect(session.setPositionState).toHaveBeenLastCalledWith(undefined);

    store.setDuration(Infinity);
    await nextTick();
    expect(session.setPositionState).toHaveBeenLastCalledWith(undefined);

    store.setDuration(120);
    store.currentTime = 30;
    await nextTick();
    expect(session.setPositionState).toHaveBeenLastCalledWith({
      duration: 120,
      position: 30,
    });

    store.currentTime = 150;
    await nextTick();
    expect(session.setPositionState).toHaveBeenLastCalledWith({
      duration: 120,
      position: 120,
    });
  });

  it("survives a browser that rejects an action", () => {
    session.rejectStop = true;
    expect(() => start()).not.toThrow();
    expect(session.handlers.has("play")).toBe(true);
    expect(session.handlers.has("seekforward")).toBe(true);
  });

  it("clears handlers and metadata on dispose", async () => {
    const store = useSoundtrackPlayer();
    start();
    store.loadPlaylist([track(1), track(2)], {});
    store.play(track(1), {});
    store.setPlaying(true);
    await nextTick();
    expect(session.handlers.size).toBeGreaterThan(0);

    scope.stop();
    expect(session.handlers.size).toBe(0);
    expect(session.metadata).toBeNull();
    expect(session.playbackState).toBe("none");
  });

  it("does nothing when the API is missing", async () => {
    Reflect.deleteProperty(navigator, "mediaSession");
    expect("mediaSession" in navigator).toBe(false);
    const store = useSoundtrackPlayer();
    expect(() => start()).not.toThrow();
    store.play(track(1), {});
    await nextTick();
    expect(session.metadata).toBeNull();
    expect(session.handlers.size).toBe(0);
  });

  it("sets no metadata when MediaMetadata is unavailable", async () => {
    vi.stubGlobal("MediaMetadata", undefined);
    const store = useSoundtrackPlayer();
    start();
    store.play(track(1), {});
    store.setPlaying(true);
    await nextTick();
    expect(session.metadata).toBeNull();
    expect(session.playbackState).toBe("playing");
  });
});
