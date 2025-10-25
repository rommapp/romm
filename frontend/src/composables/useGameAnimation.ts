import { useLocalStorage } from "@vueuse/core";
import { computed, type Ref, type ShallowRef } from "vue";
import type { VImg } from "vuetify/lib/components/VImg/VImg.js";
import type { BoxartStyleOption } from "@/components/Settings/UserInterface/Interface.vue";
import storeRoms from "@/stores/roms";
import type { SimpleRom, SearchRom } from "@/stores/roms";
import { isCDBasedSystem } from "@/utils";

export const ANIMATION_DELAY = 500;

export const CD_ANIMATION_CONFIG = {
  maxRotationSpeed: 5000, // deg/sec (adjust top speed)
  accelerationRate: 2500, // deg/sec^2 (how fast it accelerates)
  decelerationRate: -1500, // deg/sec^2 (how fast it decelerates)
};

export function useGameAnimation({
  rom,
  accelerate,
  coverSrc,
  vImgRef,
}: {
  rom: SimpleRom | SearchRom;
  accelerate: Ref<boolean>;
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
  let cdAngle = 0; // current rotation in degrees
  let cdVelocity = 0; // degrees / second
  let cdLastTimestamp: number | null = null;
  let cAnimationId: number | null = null;

  const stepCD = (timestamp: number) => {
    const imageElement = vImgRef?.value?.image;
    if (!imageElement) return;

    if (cdLastTimestamp === null) cdLastTimestamp = timestamp;
    const deltaTime = (timestamp - cdLastTimestamp) / 1000; // in seconds
    cdLastTimestamp = timestamp;

    const { accelerationRate, decelerationRate, maxRotationSpeed } =
      CD_ANIMATION_CONFIG;

    // Update velocity and angle with acceleration
    cdVelocity +=
      (accelerate.value ? accelerationRate : decelerationRate) * deltaTime;
    cdVelocity = Math.min(maxRotationSpeed, Math.max(0, cdVelocity));
    cdAngle = (cdAngle + cdVelocity * deltaTime) % 360;

    // Animate the rotation of the CD
    imageElement.style.transform = `rotate(${cdAngle}deg)`;

    if (cdVelocity > 0 || accelerate.value) {
      cAnimationId = requestAnimationFrame(stepCD);
    } else {
      // Stop the animation if the CD is no longer moving
      stopCDAnimation();
    }
  };

  const animateSpinCD = () => {
    if (!animateCD.value) return;

    cdLastTimestamp = null;
    stopCDAnimation();
    cAnimationId = requestAnimationFrame(stepCD);
  };

  const animateLoadCD = () => {
    if (!animateCD.value) return;

    const container = vImgRef?.value?.$el;
    const imageElement = vImgRef?.value?.image;
    if (!container || !imageElement) return;

    // Set the CD spinning at max speed
    cdVelocity = CD_ANIMATION_CONFIG.maxRotationSpeed;

    // Apply snap-down animation
    container.style.transition =
      "transform 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55)";
    container.style.transform = `translateY(${container.offsetHeight}px) scale(0.9)`;
  };

  const stopCDAnimation = () => {
    if (cAnimationId !== null) {
      cancelAnimationFrame(cAnimationId);
      cAnimationId = null;
    }
  };

  /* Cartridge animation */
  const animateLoadCart = () => {
    if (!animateCartridge.value) return;

    const container = vImgRef?.value?.$el;
    const imageElement = vImgRef?.value?.image;
    if (!container || !imageElement) return;

    // Apply snap-down animation
    imageElement.style.transition =
      "transform 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55)";
    imageElement.style.transform = `translateY(${container.offsetHeight}px) scale(0.9)`;
  };

  return {
    boxartStyleCover,
    animateCD,
    animateCartridge,
    stepCD,
    animateSpinCD,
    animateLoadCD,
    stopCDAnimation,
    animateLoadCart,
  };
}
