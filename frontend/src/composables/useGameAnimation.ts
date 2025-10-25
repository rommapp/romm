/**
 * This composable is used to animate the game card and play button.
 * It will spin CD based games on hover and load cartridge based games on play.
 */
import { useLocalStorage } from "@vueuse/core";
import { computed, ref, type Ref, type ShallowRef } from "vue";
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
  const st = window.getComputedStyle(el);
  const tr = st.transform;
  if (!tr || tr === "none") return 0;

  const m = tr.match(/\(([^)]+)\)/);
  if (!m) return 0;

  const values = m[1].split(",").map((v) => parseFloat(v.trim()));
  if (tr.startsWith("matrix3d")) {
    // matrix3d(...) has 16 values, translation is at indexes 12,13,14 (tx, ty, tz)
    return values[13] || 0; // ty
  } else {
    // matrix(a, b, c, d, tx, ty) -> ty is index 5
    return values[5] || 0;
  }
}

export function useGameAnimation({
  rom,
  coverSrc,
  vImgRef,
  accelerate = ref(false),
}: {
  rom: SimpleRom | SearchRom;
  accelerate?: Ref<boolean>;
  coverSrc?: string;
  vImgRef?: Readonly<ShallowRef<VImg | null>>;
}) {
  const romsStore = storeRoms();
  const boxartStyle = useLocalStorage<BoxartStyleOption>(
    "settings.boxartStyle",
    "cover",
  );

  // User selected alternative cover image
  const boxartStyleCover = computed(() => {
    if (
      coverSrc ||
      !romsStore.isSimpleRom(rom) ||
      boxartStyle.value === "cover"
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
    const container = vImgRef?.value?.$el;
    const imageElement = vImgRef?.value?.image;
    if (!container || !imageElement) return;

    if (lastTimestamp === null) lastTimestamp = timestamp;
    const deltaTime = (timestamp - lastTimestamp) / 1000; // in seconds
    lastTimestamp = timestamp;

    const { accelerationRate, decelerationRate, maxRotationSpeed } =
      ANIMATION_CONFIG;

    // Update velocity and angle with acceleration
    velocity +=
      (accelerate.value ? accelerationRate : decelerationRate) * deltaTime;
    velocity = Math.min(maxRotationSpeed, Math.max(0, velocity));
    angle = (angle + velocity * deltaTime) % 360;

    console.log(angle, velocity);

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

    if (velocity > 0 || accelerate.value) {
      animationID = requestAnimationFrame(spinCD);
    } else {
      // Stop the animation if the CD is no longer moving
      stopCDAnimation();
    }
  };

  const setTransitionCSS = () => {
    const imageElement = vImgRef?.value?.image;
    if (!imageElement) return;
    imageElement.style.transition = ANIMATION_CONFIG.transitionCSS;
  };

  const animateCDSpin = () => {
    if (!animateCD.value) return;

    lastTimestamp = null;
    setTransitionCSS();
    stopCDAnimation();
    animationID = requestAnimationFrame(spinCD);
  };

  const animateCDLoad = () => {
    if (!animateCD.value) return;
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

    const container = vImgRef?.value?.$el;
    const imageElement = vImgRef?.value?.image;
    if (!container || !imageElement) return;

    // Apply snap-down animation
    setTransitionCSS();
    imageElement.style.transform = ANIMATION_CONFIG.transformCSS(0);
    imageElement.style.marginTop = `${container.offsetHeight / 3}px`;
  };

  return {
    boxartStyleCover,
    animateCD,
    animateCartridge,
    animateCDSpin,
    animateCDLoad,
    stopCDAnimation,
    animateLoadCart,
  };
}
