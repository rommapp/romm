import { useLocalStorage } from "@vueuse/core";
import type { InputAction } from "../input/actions";

const sfxEnabled = useLocalStorage("console.sfxEnabled", true);

export function setSfxEnabled(enabled: boolean): void {
  sfxEnabled.value = enabled;
}

export function getSfxEnabled(): boolean {
  return sfxEnabled.value;
}

let ctx: AudioContext | null = null;
function ensureCtx() {
  if (ctx) return ctx;
  if (typeof window === "undefined") return null;
  if (!window.AudioContext) return null;

  ctx = new window.AudioContext();
  return ctx;
}

export type SfxType =
  | "move"
  | "confirm"
  | "back"
  | "error"
  | "delete"
  | "favorite";

interface ClickOpts {
  toneHz?: number; // fundamental pitch component
  noise?: number; // 0..1 noise mix
  duration?: number; // seconds
  gain?: number; // peak gain
  lowpass?: number; // low-pass cutoff
  pitchDecay?: number; // seconds until pitch falls
  startFreq?: number; // optional sweep start frequency
}

function playClick(opts: ClickOpts = {}) {
  const audio = ensureCtx();
  if (!audio) return;
  const now = audio.currentTime;
  const {
    toneHz = 420,
    noise = 0.35,
    duration = 0.11,
    gain = 0.18,
    lowpass = 3200,
    pitchDecay = 0.04,
    startFreq,
  } = opts;

  const master = audio.createGain();
  master.gain.setValueAtTime(gain, now);
  master.gain.exponentialRampToValueAtTime(0.0008, now + duration);

  // Tone (short sine/square blend for soft attack)
  const osc = audio.createOscillator();
  osc.type = "sine";
  const baseFreq = startFreq ?? toneHz;
  osc.frequency.setValueAtTime(baseFreq, now);
  if (startFreq) {
    // gentle sweep toward toneHz
    osc.frequency.exponentialRampToValueAtTime(toneHz, now + pitchDecay);
  } else {
    // tiny downward drift for organic feel
    osc.frequency.exponentialRampToValueAtTime(
      Math.max(40, toneHz * 0.9),
      now + pitchDecay,
    );
  }

  // Light saturation via waveshaper
  const shaper = audio.createWaveShaper();
  const curve = new Float32Array(128);
  for (let i = 0; i < curve.length; i++) {
    const x = (i / (curve.length - 1)) * 2 - 1;
    curve[i] = Math.tanh(x * 1.5);
  }
  shaper.curve = curve;

  const toneGain = audio.createGain();
  toneGain.gain.setValueAtTime(1, now);
  toneGain.gain.exponentialRampToValueAtTime(0.001, now + duration * 0.9);

  osc.connect(shaper).connect(toneGain).connect(master);

  // Noise burst
  if (noise > 0) {
    const noiseBuf = audio.createBuffer(
      1,
      Math.max(1, audio.sampleRate * duration),
      audio.sampleRate,
    );
    const data = noiseBuf.getChannelData(0);
    for (let i = 0; i < data.length; i++)
      data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
    const noiseSrc = audio.createBufferSource();
    noiseSrc.buffer = noiseBuf;
    const nGain = audio.createGain();
    nGain.gain.setValueAtTime(noise, now);
    nGain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    noiseSrc.connect(nGain).connect(master);
    noiseSrc.start(now);
    noiseSrc.stop(now + duration);
  }

  // Filtering for softness
  const lp = audio.createBiquadFilter();
  lp.type = "lowpass";
  lp.frequency.setValueAtTime(lowpass, now);
  lp.frequency.exponentialRampToValueAtTime(
    lowpass * 0.6,
    now + duration * 0.6,
  );
  master.connect(lp).connect(audio.destination);

  osc.start(now);
  osc.stop(now + duration);
}

export function playSfx(kind: SfxType) {
  if (!sfxEnabled.value) return;

  // Lazy resume (required on some browsers until user gesture)
  ensureCtx()
    ?.resume()
    .catch((error) => {
      console.error("Error resuming audio", error);
    });
  switch (kind) {
    case "move":
      playClick({
        toneHz: 860,
        noise: 0.1,
        duration: 0.02,
        gain: 0.085,
        lowpass: 2800,
        pitchDecay: 0.035,
      });
      break;
    case "confirm":
      playClick({
        toneHz: 680,
        startFreq: 760,
        noise: 0.12,
        duration: 0.12,
        gain: 0.1,
        lowpass: 3000,
      });
      setTimeout(
        () =>
          playClick({
            toneHz: 880,
            noise: 0.08,
            duration: 0.07,
            gain: 0.11,
            lowpass: 3100,
          }),
        55,
      );
      break;
    case "back":
      playClick({
        toneHz: 300,
        noise: 0.2,
        duration: 0.085,
        gain: 0.12,
        lowpass: 1700,
      });
      break;
    case "error":
      playClick({
        toneHz: 180,
        noise: 0.4,
        duration: 0.18,
        gain: 0.22,
        lowpass: 1500,
      });
      setTimeout(
        () =>
          playClick({
            toneHz: 140,
            noise: 0.25,
            duration: 0.14,
            gain: 0.16,
            lowpass: 1300,
          }),
        70,
      );
      break;
    case "delete":
      playClick({
        toneHz: 260,
        noise: 0.35,
        duration: 0.11,
        gain: 0.2,
        lowpass: 1600,
      });
      setTimeout(
        () =>
          playClick({
            toneHz: 180,
            noise: 0.3,
            duration: 0.09,
            gain: 0.16,
            lowpass: 1400,
          }),
        55,
      );
      break;
    case "favorite":
      playClick({
        toneHz: 600,
        startFreq: 540,
        noise: 0.18,
        duration: 0.09,
        gain: 0.17,
        lowpass: 3000,
      });
      setTimeout(
        () =>
          playClick({
            toneHz: 950,
            startFreq: 900,
            noise: 0.1,
            duration: 0.07,
            gain: 0.13,
            lowpass: 3400,
          }),
        50,
      );
      break;
  }
}

// map input actions to sfx categories
export function sfxForAction(action: InputAction): SfxType | undefined {
  switch (action) {
    case "moveLeft":
    case "moveRight":
    case "moveUp":
    case "moveDown":
      return "move";
    case "confirm":
      return "confirm";
    case "back":
      return "back";
    case "delete":
      return "delete";
    case "toggleFavorite":
      return "favorite";
    default:
      return undefined;
  }
}
