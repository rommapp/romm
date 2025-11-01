/**
 * This composable is used to animate the game card and play button.
 * It will spin CD based games on hover and load cartridge based games on play.
 */
import { useLocalStorage } from "@vueuse/core";
import { computed, ref, watch, type Ref, type ShallowRef } from "vue";
import type { VImg } from "vuetify/lib/components/VImg/VImg.js";
import type { BoxartStyleOption } from "@/components/Settings/UserInterface/Interface.vue";
import storeRoms from "@/stores/roms";
import type { SimpleRom, SearchRom } from "@/stores/roms";
import { isCDBasedSystem } from "@/utils";

export const ANIMATION_DELAY = 500;

export const ANIMATION_CONFIG = {
  maxRotationSpeed: 5000, // deg/sec (adjust top speed)
  accelerationRate: 2500, // deg/sec^2 (how fast it accelerates)
  decelerationRate: -1500, // deg/sec^2 (how fast it decelerates)
  transitionCSS: "margin 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55)",
  transformCSS: (angle: number) => `rotate(${angle}deg)`,
  transformOrigin: (offset: number) => `center calc(50% + ${offset}px)`,
};

function getTranslateY(el: HTMLElement) {
  const transform = window.getComputedStyle(el).transform;
  if (!transform || transform === "none") return 0;

  try {
    const matrix = new DOMMatrix(transform);
    return matrix.m42; // m42 is the ty value (vertical translation)
  } catch (e) {
    console.error("Failed to parse transform matrix:", e);
    return 0;
  }
}

export function useGameAnimation({
  rom,
  coverSrc,
  coverRef,
  videoRef,
  forceBoxart,
  isHovering = ref(false),
}: {
  rom: SimpleRom | SearchRom;
  coverSrc?: string;
  coverRef?: Readonly<ShallowRef<VImg | null>>;
  videoRef?: Readonly<ShallowRef<HTMLVideoElement | null>>;
  forceBoxart?: BoxartStyleOption;
  isHovering?: Ref<boolean>;
}) {
  const romsStore = storeRoms();
  const _boxartStyle = useLocalStorage<BoxartStyleOption>(
    "settings.boxartStyle",
    "cover_path",
  );
  const disableAnimations = useLocalStorage(
    "settings.disableAnimations",
    false,
  );

  const boxartStyle = computed(() => {
    return forceBoxart || _boxartStyle.value;
  });

  // User selected alternative cover image
  const boxartStyleCover = computed(() => {
    if (
      coverSrc ||
      !romsStore.isSimpleRom(rom) ||
      boxartStyle.value === "cover_path"
    )
      return null;
    const ssMedia = rom.ss_metadata?.[boxartStyle.value];
    const gamelistMedia = rom.gamelist_metadata?.[boxartStyle.value];
    return ssMedia || gamelistMedia;
  });

  const animateCD = computed(() => {
    return (
      boxartStyle.value === "physical_path" &&
      Boolean(boxartStyleCover.value) &&
      romsStore.isSimpleRom(rom) &&
      isCDBasedSystem(rom.platform_slug)
    );
  });

  const animateCartridge = computed(() => {
    return (
      boxartStyle.value === "physical_path" &&
      Boolean(boxartStyleCover.value) &&
      romsStore.isSimpleRom(rom) &&
      !isCDBasedSystem(rom.platform_slug)
    );
  });

  /* CD animations */
  let angle = 0; // current rotation in degrees
  let velocity = 0; // degrees / second
  let lastTimestamp: number | null = null;
  let animationID: number | null = null;
  let animateLoad = false;

  const spinCD = (timestamp: number) => {
    const container = coverRef?.value?.$el;
    const imageElement = coverRef?.value?.image;
    if (!container || !imageElement) return;

    if (lastTimestamp === null) lastTimestamp = timestamp;
    const deltaTime = (timestamp - lastTimestamp) / 1000; // in seconds
    lastTimestamp = timestamp;

    const { accelerationRate, decelerationRate, maxRotationSpeed } =
      ANIMATION_CONFIG;

    // Update velocity and angle with acceleration
    velocity +=
      (isHovering.value ? accelerationRate : decelerationRate) * deltaTime;
    // Clamp the velocity
    velocity = Math.min(maxRotationSpeed, Math.max(0, velocity));
    angle = (angle + velocity * deltaTime) % 360;

    if (animateLoad) {
      // Set the CD spinning at max speed
      velocity = ANIMATION_CONFIG.maxRotationSpeed;

      // Apply snap-down animation
      imageElement.style.marginTop = `${container.offsetHeight}px`;
      imageElement.style.transformOrigin = ANIMATION_CONFIG.transformOrigin(
        getTranslateY(imageElement),
      );
    }

    // Animate rotation of the CD
    imageElement.style.transform = ANIMATION_CONFIG.transformCSS(angle);

    if (velocity > 0 || isHovering.value) {
      animationID = requestAnimationFrame(spinCD);
    } else {
      // Stop the animation if the CD is no longer moving
      stopCDAnimation();
    }
  };

  const setTransitionCSS = () => {
    const imageElement = coverRef?.value?.image;
    if (!imageElement) return;
    imageElement.style.transition = ANIMATION_CONFIG.transitionCSS;
  };

  const animateCDSpin = () => {
    if (!animateCD.value) return;
    if (disableAnimations.value) return;

    lastTimestamp = null;
    setTransitionCSS();
    stopCDAnimation();
    animationID = requestAnimationFrame(spinCD);
  };

  const animateCDLoad = () => {
    if (!animateCD.value) return;
    if (disableAnimations.value) return;
    setTransitionCSS();
    animateLoad = true;
  };

  const stopCDAnimation = () => {
    if (animationID !== null) {
      cancelAnimationFrame(animationID);
      animationID = null;
      animateLoad = false;
    }
  };

  /* Cartridge animation */
  const animateLoadCart = () => {
    if (!animateCartridge.value) return;
    if (disableAnimations.value) return;

    const container = coverRef?.value?.$el;
    const imageElement = coverRef?.value?.image;
    if (!container || !imageElement) return;

    // Apply snap-down animation
    setTransitionCSS();
    imageElement.style.transform = ANIMATION_CONFIG.transformCSS(0);
    imageElement.style.marginTop = `${container.offsetHeight / 3}px`;
  };

  /* Video player */
  let hoverTimeout: number | null = null;
  const isVideoPlaying = ref(false);

  const localVideoPath = computed(() => {
    if (!romsStore.isSimpleRom(rom)) return null;
    // Only play video if boxart style is miximage
    if (boxartStyle.value !== "miximage_path") return null;
    const ssVideo = rom.ss_metadata?.video_path;
    const gamelistVideo = rom.gamelist_metadata?.video_path;
    return ssVideo || gamelistVideo || null;
  });

  const playVideoEnabled = computed(() => {
    return (
      boxartStyle.value === "miximage_path" && Boolean(localVideoPath.value)
    );
  });

  const playVideo = () => {
    if (isVideoPlaying.value) return;
    if (!playVideoEnabled.value) return;

    // Start video after 1.5 seconds if video path exists
    hoverTimeout = window.setTimeout(async () => {
      if (videoRef?.value) {
        videoRef.value.load();
        videoRef.value
          .play()
          .then(() => {
            isVideoPlaying.value = true;
          })
          .catch(() => {
            isVideoPlaying.value = false;
          });
      }
    }, 1500);
  };

  const stopVideo = () => {
    isVideoPlaying.value = false;
    if (hoverTimeout) {
      clearTimeout(hoverTimeout);
      hoverTimeout = null;
    }
    if (videoRef?.value) {
      videoRef.value.pause();
      videoRef.value.currentTime = 0;
    }
  };

  watch(
    isHovering,
    (hovering) => {
      if (disableAnimations.value) return;
      if (hovering) {
        animateCDSpin();
        playVideo();
      } else {
        stopVideo();
      }
    },
    { immediate: true },
  );

  watch(disableAnimations, (disabled) => {
    if (disabled) {
      stopCDAnimation();
    }
  });

  return {
    boxartStyle,
    boxartStyleCover,
    animateCD,
    animateCartridge,
    localVideoPath,
    isVideoPlaying,
    animateCDSpin,
    animateCDLoad,
    stopCDAnimation,
    animateLoadCart,
    playVideo,
    stopVideo,
  };
}
